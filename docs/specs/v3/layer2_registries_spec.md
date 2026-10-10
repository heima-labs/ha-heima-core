# Heima v3 — Layer 2: Registries

**Status:** Defined V3 contract. Not implemented.
**Layer:** 2 of 8. Builds on Layer 1 (`docs/specs/v3/layer1_substrate_spec.md` — `HouseFact`,
`Provenance`, `Location`, `Zone`, `EvidenceValue`) and Layer 0 (`docs/specs/v3/layer0_runtime_spec.md`
— `Window`, `FactSource`, Persistence). This document does not restate either contract; it assumes the
reader has them, since all three are the same v3 architecture and Layer 2 does not exist without
them.

This document is self-contained with respect to Heima's v2 specs: it defines what Layer 2 is and
does without assuming the reader has read them.

## Normative precedence

This document defines the current V3 Layer-2 design contract. Open corrections are tracked in
the CA4 backlog; runtime implementation is a separate phase. When implemented, if code and
spec diverge, the divergence must be resolved explicitly — code is a
reference implementation, not the source of truth.

---

## 1. Purpose

Layer 2 is where raw Home Assistant data becomes `HouseFact`s, and where several `HouseFact`s
become one derived `HouseFact`. Three concepts:

1. **`Sensor`** — registers exactly one HA read binding as exactly one `fact_type` at exactly one
   `Location`, with an `Interpretation` that turns the raw value from that binding into a typed
   `HouseFact.value`.
2. **`FusionRule`** — how N facts (`Sensor`-produced, or produced by another `FusionRule` — §5.6)
   become one derived `HouseFact`, via one of five closed strategies.
3. **`Actuator`** — an inventory record of a commandable entity. Never itself a fact producer, never
   itself a command.

Layer 2 collapses **9 independently-invented entity-list mechanisms** found in the current codebase
(`occupancy_sources`, `learning_sources`, room `signals`, `house_signal_entities`,
`media_active_entities`, `sleep_charging_entities`, `work_activity_entities`,
`context_signal_entities`, and `ExternalContext`'s `{slot: entity_id}` mapping) into one registry —
each becomes a `Sensor` record distinguished by `fact_type`, not a separately-validated, separately
selected list with its own admin-panel section.

### 1.1 V3 clean-start cutover

This is a design derivation, **not a migration contract**. V3 does not import or translate any V2
entity list, configuration, `HouseFact`/event history, runtime checkpoint, or learned model. A V3
installation starts with new, explicit registry configuration and empty fact and learning stores. An
operator must explicitly create or reset that V3 configuration; implementation must never overwrite
V2 options in place or silently synthesize `Sensor`, `FusionRule`, `Actuator`, or `Zone` records.

An exported V2 artifact may be retained outside V3 as rollback/reference material, but no V3 runtime
path may read, bind, interpret, or derive state from it. This deliberately removes compatibility
branches and data conversion from both bootstrap and the cycle hot path. The exact user-interface
mechanism for the explicit cutover belongs to Layer 8; its outcome is always the same clean V3 state.

## 2. Scope

Layer 2 is responsible for:
- `Sensor`, `ReadBinding`, and `Interpretation` — which HA entity/state/attribute/calendar slot Heima
  reads, and how that raw input becomes a typed `HouseFact.value`;
- `FusionRule` and its five strategies — how multiple facts combine into one derived fact, which of
  Layer 1's confidence functions (§4.2 of the Layer 1 spec) each strategy uses, and the
  registration-time ordering that lets a `FusionRule` consume another `FusionRule`'s output (§5.6);
- the separate, core-owned formula registry `FormulaStrategy` (one of the five) points into;
- `Actuator` — the commandable-entity inventory.

Layer 2 is **not** responsible for:
- the `HouseFact`/`Provenance` shape, or the confidence/availability rules that govern them — those
  are Layer 1's; Layer 2 only decides *which* rule applies to *which* producer, per Layer 1's own
  boundary (Layer 1 §4.2: "Layer 1 has no visibility into [what's being combined]... Layer 2 [does]").
- storage, timing, or provenance mechanics — Layer 0's, unchanged, consumed as-is.
- issuing commands to an `Actuator` — that is a Reaction's job (Layer 5); an `Actuator` record here is
  inventory only, never itself a command.
- semantic resolution that reads `Sensor`/`FusionRule` output (Layer 4) or policy that acts on it (Layer 5).

### 2.1 Extension boundary and non-goals

- Third-party registration of `Interpretation`, `FusionStrategy`, or `RegisteredFormula`. These are
  closed, core-owned semantic registries in V3, not a deferred plugin API: a future general mechanism
  enters the core only with a new specification version, validator, reload-impact semantics, and
  acceptance coverage. This preserves the hot-path guarantees for value shape, availability,
  confidence, DAG ordering, and failure handling rather than exposing an immature compatibility
  contract to arbitrary callables.
- A Layer-7 plugin may instead be a separately staged fact producer: it declares its `FactTypeClaim`
  and produces ordinary `HouseFact`s under the Layer 0/1 contracts. Its facts may feed the existing
  closed strategies, but it cannot alter their union, register a formula, or dynamically import code
  into a Sensor/Fusion execution path. The future Layer-7 lifecycle defines how such a producer is
  invoked; this Layer-2 boundary defines only what it cannot extend.
- Redesigning the `Room`/device inventory model — `where: Location` and `device_id` reference it,
  Layer 2 does not own it (same boundary Layer 1 already states for `room_id`).

### 2.2 Performance contract — no blocking I/O on the hot path

Every execution point this layer introduces runs on the engine's hot, same-cycle path: a `Sensor`'s
`Interpretation` decoding raw input already extracted by its `ReadBinding` (§3.1/§4), a
`FusionRule`'s strategy combining current facts (§5.1), and specifically `RegisteredFormula.compute`
(§5.3) — the one place in this layer where
control passes to an arbitrary core-team-authored `Callable`, not a closed strategy the engine
evaluates itself. All three must be pure, synchronous, and bounded: no network calls, no disk reads,
no blocking waits of any kind. Any input a decoder/strategy/formula needs must already be present in
the `HouseFact`s and registry data handed to it — never fetched fresh at evaluation time.

This restates architecture invariant #2 (no blocking I/O on the hot path) explicitly for this layer's
own execution points, rather than leaving it assumed. It matters most for `RegisteredFormula.compute`
specifically: its result type (`FormulaResult | None`, §5.3) makes confidence handling explicit but
does not itself prevent a slow or blocking implementation — nothing in the type system enforces this, so
it is a normative constraint on every registration, verified by code review at registration time, not
something a runtime check can generally guarantee.

### 2.3 Composition-time uniqueness: one state producer per `(fact_type, Location)`

**Resolved 2026-09-05; widened 2026-09-09.** Every state `(fact_type, Location)` pair has exactly one
producer across the composed system — a `Sensor` or a `FusionRule` here, never both, and never two of
either. This is what makes
`FactRef` addressing (§5) well-defined in the first place: "the current `HouseFact` for this
`fact_type` at this `Location`" presupposes there is exactly one such producer to ask. §5.6's
registration-time topological sort presupposes the same thing when it builds an edge from A to B
"whenever A's `produces`/`where` matches one of B's `inputs`" — an ambiguous match (two producers
both claiming the same pair) would make the dependency graph itself ill-defined, not merely an
awkward configuration.

A registration (`Sensor.fact_type`/`Sensor.where`, or `FusionRule.produces`/`FusionRule.where`) that
collides with an already-registered state producer's `(fact_type, Location)` is rejected at
composition time, loudly, never silently accepted — the same discipline §5.6 already applies to
`FusionRule` dependency cycles. Layer 2 contributes its static state claims to Layer 0 §4's bootstrap
`FactTypeClaim`/global producer pass; it also rejects a fact type owned by another layer's claim, such
as Layer 0's reserved `manual_hold.lifecycle` event claim. This is a startup/configuration lookup only, never an
evaluation-path lookup.

That pass also resolves each producer `Location` before it is admitted: `scope="room"` must name a
registered room; every id in `scope="rooms"` must name a registered room; and `scope="zone"` must name
a registered Zone. Zone and Topology registration perform their own Room-registry reference resolution
under Layer 1 §6/§7. Thus construction may remain free of registry ordering, but no unknown spatial
reference can reach a running `Sensor` or `FusionRule`.

`Sensor.sensor_id` is unique among Sensors and `FusionRule.fusion_id` is unique among FusionRules
within a candidate generation. Registry-id uniqueness is checked independently of output-claim
uniqueness: two records cannot share an id even if they claim different facts.

`Sensor` and `FusionRule` produce only `state` facts. Event facts are emitted only by the owning
subsystem declared in Layer 0 §4; they are not `FactRef` inputs and cannot be recreated through a
generic Sensor or Fusion registration.

### 2.4 Numeric and cardinality validation

All static numeric and cardinality constraints are checked when a `Sensor`, `FusionRule`, or
`RegisteredFormula` is registered. An invalid registration is rejected loudly before it can enter the
hot evaluation path; it is never normalized, clamped, or allowed to fail unpredictably later. Every
quantitative number below must be a non-boolean `int` or finite `float` (`NaN` and either infinity are
invalid); a `bool` is accepted only where the field is explicitly boolean. This applies equally to
numeric formula results and payload fields validated by a formula compiler, while preserving boolean
fact values as valid `EvidenceValue`s.

- `Sensor.reliability` is in `[0.0, 1.0]`.
- A `Sensor` whose fact type is exactly `occupancy.evidence.<kind>.<sensor_id>` at a room, or
  `presence.evidence.<kind>.<sensor_id>` at `casa`, declares a non-empty
  `physical_evidence_admission` and `correlation_group`; the suffix equals that Sensor's stable
  `sensor_id`. Every other Sensor leaves both fields `None`. These are explicit per-reading choices:
  no HA device class, entity category, or `reliability` value supplies an implicit default. A
  person-evidence `<kind>` is valid only when the registered interpretation maps an explicit person
  classification; generic movement, unknown-object, and another object classification are not
  person evidence.
- Every static value that an interpretation can emit passes Layer 1's pure
  `validate_house_fact_value` during staging: every `MappingInterpretation.mapping` value and its
  `default` unless it is `NO_DEFAULT`, every `Bucket.label`, and every `KeywordClassifier` category
  key. A generation with an oversized, over-nested, non-finite, or otherwise invalid would-be
  `HouseFact.value` is rejected before reload. `NumericInterpretation` and formula result values are
  necessarily dynamic and retain their explicit runtime validation; formula *configuration* remains
  governed by its separate §5.3 configuration contract.
- A `BucketInterpretation` has at least one `Bucket`; every numeric `upper_bound` is finite and
  strictly greater than the preceding numeric bound; `upper_bound=None` occurs exactly once and only
  on the final bucket. This makes the vocabulary ordered and total over the real line.
- `CalendarWindowReadBinding` pairs only with `CalendarInterpretation`, and
  `CalendarInterpretation` pairs only with `CalendarWindowReadBinding`. `StateReadBinding` and
  `AttributeReadBinding` pair only with `MappingInterpretation`, `NumericInterpretation`, or
  `BucketInterpretation`. These are staging-time type-shape checks, not runtime guesses (§4).
- `Actuator.actuator_id` is unique and stable within the generation, and every HA `entity_id` belongs
  to exactly one `Actuator`. The same entity may independently back any number of `Sensor`s: reading
  and commanding are distinct roles. If `opening_id` is set, it resolves in the candidate `Topology`
  and `where` is exactly `Location(scope="room", room_id=<Opening.room_id>)`; when it is absent, no
  opening relation is implied or required. `device_id` is intentionally not unique.
- Every `FusionRule.inputs` tuple is non-empty and has no repeated logical `FactRef` key
  `(fact_type, where, previous_cycle)`. `DirectStrategy`'s existing exact-one rule remains
  stricter where it applies. A current-cycle self-reference and an explicitly permitted
  `previous_cycle` self-reference are distinct observations only for a FormulaStrategy that
  authorizes that self-memory (§5.8); repeating either exact reference is rejected. The same
  producer may remain an input to several different FusionRules.
- `UnanimityStrategy.min_available` is an integer (not `bool`) in `[1, len(inputs)]`.
- For `WeightedQuorumStrategy`, every explicit weight is finite and strictly positive. Negative or
  zero weights are invalid: a weight expresses the amount of evidence a `True` vote contributes, not
  an inverse correlation or a counter-vote. The latter must be normalized into a semantically oriented
  fact before fusion, or expressed by `FormulaStrategy`. `threshold` is finite and in
  `(0, total_configured_weight]`; `min_available_weight` is finite and in
  `[0, total_configured_weight]`, where an input omitted from `weights` contributes its default 1.0.
- `RegisteredFormula.min_inputs` is an integer (not `bool`) in `[1, len(owning FusionRule.inputs)]`.
  For `confidence_mode="continuous"`, `scale` is finite and `> 0` and `floor` is finite and in
  `[0.0, 1.0]`; the other two modes prohibit both fields. The mode-specific result validation in §5.3
  remains the runtime guard for formula-produced values.
- `physical_evidence.weighted_evidence` requires a configuration payload that compiles to a
  `PhysicalEvidenceWeightedConfig`. The environmental solar-incidence and
  humidity-ratio formulas have their own closed compiled configurations in
  §5.3; every other Initial-V3 formula requires `configuration=None`. The physical-evidence
  formula's
  bindings contain every input index exactly once, in `[0, len(inputs))`; both weights are finite,
  `true_weight > 0`, `false_weight >= 0`, and a `required_for_false` binding has
  `false_weight > 0`. `true_threshold` is in `(0, sum(true_weight)]` and `false_threshold` is in
  `(0, sum(false_weight)]` across the bindings. Bindings resolved to the same `correlation_group`
  have the same role, admission, weights, and `required_for_false` setting, so one group has one
  unambiguous effective vote profile. When the owning rule's effective true dwell is zero, every solely
  `corroborating` group's maximum possible true contribution is strictly below `true_threshold`; it
  therefore needs another independent group. A corroborating group may reach the threshold alone
  only through an owning, explicitly positive true confirmation dwell (`Window` or `Stability`).
- When `FusionRule.stability` is `Stability`, `unavailable_grace` is either `None` or a positive
  `Window`; it is invalid on a plain symmetric `Window` because that shape has no availability policy.

### 2.5 Atomic configuration reload

**Resolved 2026-09-09.** A registry reload is one immutable `RegistryGeneration`, never a sequence of
live unregister/register calls. Staging happens outside evaluation and constructs candidate Room, Zone,
Topology, Sensor, FusionRule, Actuator, formula, producer-claim, and `previous_cycle` declarations.
Before it can replace the active generation, one complete validation pass resolves every spatial
reference and checks §2.3 producer uniqueness, fact ownership, numeric/cardinality constraints,
formula availability and binding validation (§5.3), Fusion DAG order, and §5.7 source/destination
coverage against the candidate Zone memberships. Any failure rejects the whole candidate and leaves
the active generation untouched.

On success, the candidate's canonical definitions, full definition fingerprints, and per-producer
**execution semantic fingerprints** become part of one composed configuration generation (Layer 0
§4.7): its durable manifest is the activation, carries `effective_at`, and every layer swaps its
active pointer together, only between cycles. The same staging pass contributes Layer 2's producer
claims and Actuator channels to the cross-layer dependency index, so an edit that breaks a
downstream consumer requires the administrator's confirmation of the impact record before commit. A semantic fingerprint is derived
once, after all candidate references are resolved, from exactly the fields that can affect a producer's
value, availability, confidence, provenance semantics, temporal behavior, or spatial coverage. It is
not calculated in an evaluation cycle. The active generation already holds the equivalent fingerprints,
so candidate-vs-active comparison is one staging-time traversal of registrations and dependency edges;
pointer selection in the hot path remains O(1).

A full definition fingerprint still records any configuration change for audit, including display-only
metadata. A semantic fingerprint deliberately excludes such metadata: changing a display name is not a
reason to reset dwell/grace state, invalidate prior-cycle memory, or force a fact write. The
`FactSource.configuration_fingerprint` carried by a producer is its resolved execution semantic
fingerprint, not an installation-wide generation hash; persisted generation metadata retains the full
definition fingerprint when audit needs the complete administrative configuration.

The reload computes a direct-and-transitive **impact set** from those staging-time comparisons. A
producer is directly impacted when it is added, removed, relocated, or its execution semantic
fingerprint differs; this includes a changed Sensor binding/interpretation/unit contract/
source-age gate/numeric bounds/reliability, a changed
FusionRule inputs/strategy/formula configuration/stability, a Zone membership change affecting its
scope or coverage, and a changed resolved formula `(formula_id, implementation_version)`. Every
FusionRule dependent of an impacted producer is then impacted transitively through current-cycle
`FactRef`s. Validated prior-cycle self-memory has no cross-producer dependent edge; the impacted rule's
own snapshot key is invalidated by the cutover action below. The following actions are mandatory only
for that set:

- reset each impacted `FusionRule`'s ephemeral `Stability` pending transition and availability grace;
- invalidate the output `FactIdentityKey` of every impacted producer in Layer 0's
  `PreviousCycleSnapshot`, so any first new-generation `previous_cycle` read of changed semantics is
  `available=False` rather than memory computed under the old generation;
- re-evaluate and force-write each retained impacted producer even when its value is unchanged, with
  its new `FactSource.configuration_fingerprint` so write-on-change and audit see the semantic change;
- emit one terminal `available=False` state fact for each removed or relocated producer claim, so no
  old current value remains visible under an address no new producer owns.

Rules outside the impact set retain their pending stability and prior-cycle memory. An Actuator with a
changed **execution semantic** fingerprint is handled in the same transaction:
`power_recovery_policy="never"` removes its per-channel recovery snapshots; otherwise each is
usable only when the candidate Actuator semantic fingerprint and recovery policy match the
snapshot's recorded values. A mismatch
discards that snapshot rather than reconciling an intent under changed capabilities or policy; display-only
Actuator metadata does neither. Removal of an Actuator, or a changed `entity_id` for the same stable
`actuator_id`, also deletes the old endpoint's per-channel snapshots; they are never
migrated to another HA endpoint merely because the logical id stayed the same.
Layer 0 receives this resolved policy/fingerprint/entity delta
at composition commit; it never queries Layer 2’s live registry during recovery.

---

## 3. `Sensor`

```python
@dataclass(frozen=True)
class StateReadBinding:
    entity_id: str
    source: Literal["state"] = "state"

@dataclass(frozen=True)
class AttributeReadBinding:
    entity_id: str
    attribute: str
    source: Literal["attribute"] = "attribute"

@dataclass(frozen=True)
class CalendarWindowReadBinding:
    entity_id: str
    source: Literal["calendar_windows"] = "calendar_windows"

ReadBinding = StateReadBinding | AttributeReadBinding | CalendarWindowReadBinding
PhysicalEvidenceAdmission = Literal["immediate", "corroborating"]

@dataclass(frozen=True)
class UnitConversionRef:
    conversion_id: str
    version: str

@dataclass(frozen=True)
class QuantitativeUnitContract:
    source_unit: str
    canonical_unit: str
    source_unit_authority: Literal["ha_state_metadata", "declared_attribute_contract"]
    conversion_ref: UnitConversionRef | None  # None only for exact source==canonical identity

@dataclass(frozen=True)
class Sensor:
    sensor_id: str             # stable Heima logical-reading id, not an HA entity_id; non-empty and
                               # one dotted-name segment when used in a per-sensor fact namespace
    binding: ReadBinding
    where: Location            # Layer 1 §5
    fact_type: str             # Layer 1 §3 naming convention — e.g. "occupancy.evidence.motion.pir_a",
                                 # "room_signal.illuminance", "presence", "external.outdoor_temp"
    interpretation: Interpretation
    device_id: str | None = None   # HA device_registry id, reference only — never a live dependency,
                                     # same pattern as Zone↔Label (Layer 1 §6). Groups sibling
                                     # entities in the admin panel and powers "register one role,
                                     # suggest the others" discovery (e.g. a thermostat's Sensor role
                                     # suggests its hvac_unit Actuator role, same physical device).
    related_opening_id: str | None = None  # optional physical Topology reference for a reading made
                                            # at/through one opening (contact, cover position, local
                                            # illuminance, etc.). It is not a Location tier and never
                                            # an HA entity id; staging requires a room-scoped Sensor
                                            # whose room is the owning room of this Opening (§2.4).
    unit: str | None = None         # HA's unit_of_measurement expected at registration time. Together
                                     # with expected_device_class/state_class, this is a source-shape
                                     # expectation; quantitative use is governed by unit_contract (§3.3).
    unit_contract: QuantitativeUnitContract | None = None  # required for numeric/bucket interpretation
    max_source_age: Window | None = None  # optional HA report-age gate on state/attribute reads
    numeric_bounds: tuple[float, float] | None = None  # inclusive canonical-unit range, numeric only
    expected_device_class: str | None = None  # expected HA device_class for this read path when the
                                              # entity metadata actually describes that path (§3.3).
    expected_state_class: str | None = None
                                              # expected HA state_class for the read path; None is
                                              # deliberate when no state class is applicable (§3.3).
    reliability: float = 1.0        # confidence reported when available=True (§3.2) — a fixed,
                                     # declared property of this specific device, never recomputed
                                     # per cycle. Default 1.0: without a concrete evidentiary reason,
                                     # a raw reading is fully trusted (Layer 1 §4.2's "not a guess"
                                     # principle) — a value other than 1.0 requires one (e.g. a
                                     # WiFi-based presence sensor with a known false-negative rate).
                                     # Irrelevant when available=False: confidence is always None
                                     # there (§3.2) regardless of reliability, because confidence
                                     # describes trust in an observation, and there is none to trust.
    physical_evidence_admission: PhysicalEvidenceAdmission | None = None
                                     # Required only for occupancy.evidence.*.* and
                                     # presence.evidence.*.* paths. "immediate" is an explicit
                                     # assertion that this normalized semantic evidence may be a
                                     # primary positive input; "corroborating" may contribute only
                                     # through a configured quorum or confirmation path. There is no
                                     # implicit upgrade based on HA device class or reliability.
    correlation_group: str | None = None
                                     # Required with physical_evidence_admission. Same non-empty
                                     # stable id means readings share a physical/device/model
                                     # failure mode and cannot be counted independently by the
                                     # physical-evidence formula. It is never an HA entity id.
```

Every Home Assistant **readable signal path** Heima cares about is registered exactly once, here —
one registry, not several independently-configured entity lists for different purposes (§1). A
readable signal path is more precise than an entity id: one HA entity may legitimately produce
several `Sensor`s when different parts of it mean different facts (for example a `climate.*` entity's
state, `current_temperature`, and `hvac_action`; or a device whose sibling entities share the same
`device_id`). The uniqueness invariant stays `(fact_type, Location)` (§2.3), not "one `Sensor` per
entity id." What must never happen is two producers claiming the same `(fact_type, Location)`, or one
producer hiding several facts inside one bundled output.

**Per-sensor room-occupancy evidence has a reserved namespace.** A physical reading that contributes
to room occupancy produces exactly `occupancy.evidence.<kind>.<sensor_id>`, at that room's
`Location`, where `<kind>` names its normalized evidence semantics (for example `motion`, `presence`,
or `contact`) and `<sensor_id>` is this `Sensor`'s stable Heima id. The suffix is never a Home
Assistant `entity_id`: an HA rename, re-pair, or replacement can change the `binding` while preserving
the logical evidence identity and its history. Conversely, a semantically different evidence role
gets a new `sensor_id`, even if it happens to read the same HA device. This makes several PIR/mmWave
readings in one room separately addressable by `FactRef` while preserving the one-producer-per-
`(fact_type, Location)` invariant. The derived physical room fact is `occupancy.physical`; Layer 4
alone resolves the canonical semantic `occupancy`. `occupancy.physical` is the sole standardized
physical room-occupancy ground truth a core learner may bind; individual evidence facts are never
training labels. Only the evidence layer carries a per-sensor suffix.

**Casa-presence evidence follows the same boundary.** A physical or externally normalized reading
that contributes to casa presence produces `presence.evidence.<kind>.<sensor_id>` at
`Location(scope="casa")`; a Layer-2 `FusionRule` may aggregate only those declared inputs into the
boolean `presence.physical`. Layer 2 never claims the semantic `presence` fact itself.

**Physical-evidence quality is explicit and generic.** Every sensor in either reserved evidence
namespace declares both `physical_evidence_admission` and `correlation_group`; every other Sensor
must leave both unset. An integration that distinguishes a person from generic motion maps only its
declared `person` classification to a person-evidence fact (for example
`presence.evidence.vision_person.front_camera`). Generic motion, unknown-object, or object-class
observations are distinct normalized facts and cannot silently become person evidence. A camera/model
whose person classification can be confused with moving equipment is registered `corroborating`, not
`immediate`, unless an administrator deliberately accepts that risk for the specific logical reading.

`reliability` reports confidence in one observation; admission controls whether that observation may
be sufficient to establish a positive physical conclusion; correlation controls whether two readings
may accumulate as independent evidence. These are deliberately separate axes. Two sibling entities
or pipelines from one camera, bridge, or physical detector use the same `correlation_group`, even when
their `sensor_id`s and fact types differ. A single independent sensor may use its own stable group id.

`workday_entity` becomes a `Sensor` too; its calendar-override behavior is a `PrecedenceStrategy`
`FusionRule` (§5), not a property of the sensor itself. `ExternalContext`'s slots become
`Sensor(binding=StateReadBinding(entity_id="<adapter_entity>"), fact_type="external.<slot>",
where=Location(scope="casa"))` — the adapters behind them (OWM, Protezione Civile) stay ordinary HA
integrations exposing ordinary entities, not a Layer 7 concern.

`related_opening_id` gives an observation the same optional physical precision that `Actuator.opening_id`
gives a command endpoint (§2.4), without changing `Location`: a window contact, shutter-position
sensor, or illuminance sensor can identify the opening it concerns, while an ordinary room temperature
or light sensor leaves it unset. If set, the referenced opening must exist and the Sensor's `where`
must be exactly its owner room (not `casa`, `zone`, or `rooms`). A derived fact may preserve that
identity only when staging can trace every contributing physical Sensor to the same
`related_opening_id`; otherwise it is not admissible as an opening- or cover-specific binding. This
prevents a multi-window room from being silently treated as one physical aperture.

**Source-shape expectation.** `unit`, `expected_device_class`, and `expected_state_class` are the
frozen metadata expectation of the specific HA read path. They make staging validation and later
configuration-drift diagnostics possible; they do not turn Home Assistant metadata into a Heima fact
semantic or select an `Interpretation`. Quantitative unit validation/conversion
is the separate explicit `QuantitativeUnitContract` below. A path whose enclosing entity
does not describe the value it exposes (for example `weather.*` or an attribute of `climate.*`) leaves
the inapplicable expectation unset. The explicit binding and `Interpretation` remain authoritative.

### 3.1 `ReadBinding` — how HA data enters a `Sensor`

`ReadBinding` is the adapter between Home Assistant's entity model and Heima's cleaner `HouseFact`
model. It answers one question only: **which raw input is handed to `Interpretation` this cycle?**
It does not interpret, bucket, fuse, classify, or decide confidence. Those stay `Interpretation`,
`FusionRule`, and `Provenance` concerns respectively.

Three binding shapes are enough for the concrete HA surfaces Heima already uses:

- **`StateReadBinding`** reads the entity's primary `state` string. This covers binary sensors,
  switches, media players, device trackers, lock/alarm-style vocabularies, and helper entities.
- **`AttributeReadBinding`** reads one named HA state attribute. This covers multi-signal entities
  such as `climate.*` (`current_temperature`, `temperature`, `hvac_action`) without pretending the
  entire entity is one fact or forcing bespoke code outside this registry.
- **`CalendarWindowReadBinding`** reads only the raw windows active **now** for one `calendar.*`
  entity through Layer 0's `active_now` view (§3.4.1 of the Layer 0 spec). It passes raw event
  summary/start/end data to `CalendarInterpretation` (§4); category classification still happens here
  in Layer 2, never in Layer 0. A predictive Layer-5 consumer does not route future events through a
  `Sensor`: its plan stages a finite `CalendarViewRequirement` and reads the matching
  `FrozenCalendarView` from its `DecisionSnapshot` (Layer 0 §4.1, Layer 4 §5.1), retaining each
  event's start/end/summary for a decision such as notifying today about tomorrow's event. It never
  calls Layer 0's live `upcoming_starts_within` method during policy evaluation; Layer 4 only
  transports the frozen view.

The binding output is a small raw value or small sequence of raw values already available in Home
Assistant's in-memory state/context for the current cycle. It is never a network fetch, disk read, or
fresh service call. If a binding would require an external fetch to answer, that fetch belongs in the
upstream HA integration/adapter that exposes an entity, not in Layer 2's hot path.

Binding failure maps to `available=False` before `Interpretation` runs (§3.2): missing entity,
`unknown`/`unavailable` state for `StateReadBinding`, missing attribute for `AttributeReadBinding`,
or a calendar binding that cannot obtain raw event windows from Layer 0's pre-DAG calendar
extraction. An empty-but-successful calendar result is not a binding failure; it is handed to
`CalendarInterpretation`, which may then produce no category and therefore `available=False` by its
own rule (§3.2/§4).

`Sensor.device_id` stays a grouping/reference field, not the thing being read. If HA reports a
`device_id` for the bound entity, multiple `Sensor`s may share it so the admin panel can present one
physical device with several facts and actuator roles. The same physical device may also have one or
more `Actuator` records (§6); this is expected, not a modeling conflict.

### 3.2 `available` when the producer cannot form a usable fact assertion

A `Sensor` is what actually sets `Provenance.available` (Layer 1 §4.1) — this is where a usable fact
assertion is first decided, by a concrete rule, not by each producer's discretion:

- **The binding cannot produce raw input**: the entity does not exist; a state binding reads
  `unavailable` or `unknown`; an attribute binding targets a missing attribute or an entity whose
  state is unavailable; or a calendar-window binding cannot obtain raw event windows from Layer 0's
  pre-DAG calendar extraction. `available=False`, `confidence=None` (Layer 1 §4.1). The
  `Interpretation` (§4) is not run at all in this case; there is no raw input to interpret. (`value`
  carries no defined content here — Layer 1 §3 — a producer may leave it at `None`, but nothing
  downstream may rely on that.)
- **The binding succeeds, but its `Interpretation` cannot produce an interpretable value from what
  it read**: `available=False`, `confidence=None`, same as above. Whether this case can happen at all
  is **not** a fixed fact about which `Interpretation` type is in use — it is a declared property of
  the specific registration, resolved 2026-09-05 alongside collapsing three hardcoded-vocabulary
  variants into `MappingInterpretation` (§4):
  - `NumericInterpretation` and `BucketInterpretation` are total over a valid finite numeric input:
    the former returns the normalized number and the latter's ordered chain of `upper_bound`s plus its
    open-ended top bucket covers the entire real line. A raw input that fails §4's strict numeric
    parser is instead an interpretation type failure: `available=False`/`confidence=None` with a
    diagnostic, never a coerced number or a guessed bucket.
  - `MappingInterpretation` is total, or not, depending on its own `default` field (§4):
    `default=<value>` means a raw state absent from `mapping` still produces a defined value — no
    "can't interpret" case for that registration, including `default=None` when `None` is deliberately
    the produced value. `default=NO_DEFAULT` means a raw state absent from `mapping` is deliberately
    treated the same way `CalendarInterpretation`'s open vocabulary is
    (below) — an explicit, reviewable choice a `Sensor` producer makes ("I only know how to speak for
    these specific states, nothing else"), not an assumption baked into a dataclass type the way the
    three collapsed variants used to make it.
  - `CalendarInterpretation`'s `KeywordClassifier` vocabulary is admin-defined and inherently open —
    a real event can legitimately match no configured category. "No current event to classify" is the same
    case as a `MappingInterpretation(default=NO_DEFAULT)` producer running out of vocabulary, just reached
    by a different mechanism (fuzzy keyword scan vs. exact lookup, §4). Either way, this is *not* a
    value in the interpretation's own output space (there is no implicit "none" category) — it is the
    absence of a signal from this `Sensor`, which is exactly what `available=False` exists to mean,
    not a value to invent. (This is what makes `PrecedenceStrategy`'s `workday_entity` fallback,
    §5.1, actually work: it falls through to the raw entity specifically because the calendar
    `Sensor` reports `available=False` here, never because it reports some "none" value
    `PrecedenceStrategy` would have to special-case.)
- **A declared source freshness or numeric range gate fails**: for a state/attribute binding with
  `max_source_age`, the HA state's `last_reported` must be timezone-aware, no later than the current
  cycle instant, and no older than that positive `Window`. HA `last_updated` means that state or
  attributes changed, so it cannot reject an identical value that HA reported again. This gate
  proves an HA entity report, not necessarily a new physical device measurement: an integration
  that does not publish identical device readings cannot use it to prove those readings occurred.
  Setting `max_source_age` is the registration's explicit assertion that the HA entity reports
  within that maximum silent interval while healthy; an event-driven binding that only
  publishes changes leaves it `None` unless its integration separately guarantees reports.
  This is validated for shape at staging, but the physical reporting promise cannot be
  inferred or proved merely from an HA timestamp.
  A staged binding with this gate arms one ordinary Layer-0 `AtJob` with
  `basis="wall_clock"` for the first representable instant strictly after
  `last_reported + max_source_age`.
  A newer report re-arms the same job id; cancellation/replacement uses the
  shared scheduler, never a Sensor-specific timer loop. At due, a fresh
  frozen HA intake rechecks `last_reported` before declaring unavailable;
  it neither invents a report nor writes a same-value fact. Startup does not
  replay missed expiry callbacks: its first fresh intake checks the current
  age and Layer-0 process coverage already marks the interrupted interval.
  For a numeric binding with
  `numeric_bounds`, the converted canonical-unit number must be finite and within its inclusive
  ordered bounds. Otherwise the fact is `available=False`, `confidence=None` with a diagnostic;
  no previous valid value is substituted. If a report-age limit expires between cycles, the
  expiry instant is passed as a required-stream observation-gap start to Layer 0 §4.4;
  the unavailable `HouseFact` itself is emitted at the detecting cycle's instant and is
  never backdated. Staging rejects either field on an inapplicable binding,
  a nonpositive `max_source_age`, bounds other than two finite non-boolean
  numbers with lower <= upper, or a missing unit contract. Both gates enter
  the Sensor's execution fingerprint.
- **Otherwise**: the `Interpretation` produces `available=True` with a real `value` and
  `confidence=Sensor.reliability` — resolved 2026-09-05, replacing an earlier, hardcoded
  `confidence=1.0`. `reliability` defaults to `1.0`, so this is unchanged for the common case; it is
  not computed dynamically from this cycle's data, it is the fixed, declared value from the
  `Sensor`'s own registration (Layer 1 §4.2 — "a raw reading is either fully trusted or absent, no
  in-between without a concrete evidentiary reason," now an actual mechanism instead of an
  unexercised allowance).

### 3.3 Source-shape drift diagnostic — mechanism

**Resolved 2026-09-05.** Checked at the same point an `Interpretation` already reads the entity's raw
input (§3.1/§4) — the bound entity's live `unit_of_measurement`, `device_class`, and `state_class`
are already available there for state/attribute bindings, so this costs nothing beyond binding
extraction and §2.2's no-blocking-I/O contract holds unchanged. If a live, applicable metadata value
differs from its registered expectation, a diagnostic event is raised (Layer 0 §10, the same
mechanism Layer 1 §4.3 uses for an `evidence` shape violation). Device/state-class drift and
unit metadata that does not describe the bound read path remain diagnostic-only;
there is no automated correction. Quantitative unit drift is different because
it changes the meaning of a number, so the following gate also makes that
reading unavailable before `NumericInterpretation` or `BucketInterpretation`
can emit a value.

Every quantitative `Sensor` using `NumericInterpretation` or
`BucketInterpretation` has one immutable `QuantitativeUnitContract`. It names
the exact source unit, canonical Heima unit and, when these differ, one
core-registered `UnitConversionRef` whose frozen pure converter declares that
exact input/output unit pair. An exact same-unit binding uses identity with
`conversion_ref=None`. There is no implicit scaling, offset or UI-dependent
unit selection. The converted finite number is the only value passed to
numeric output or bucket thresholds, and downstream typed bindings validate
the declared canonical unit. The core unit-conversion registry is
bootstrap-frozen, versioned and pure; a changed conversion semantic version
invalidates dependent staged generations/artifacts under ordinary selective
invalidation. It never receives a raw HA object or executes on a learning or
action path.

Staging rejects a quantitative Sensor with no unit contract, empty/unknown
core unit tokens, a missing or wrong conversion for a differing unit pair,
or a mismatch between its declared canonical unit and any staged typed
consumer of that fact. The canonical unit enters the Sensor's definition
fingerprint; a change invalidates dependent consumers. With
`source_unit_authority="ha_state_metadata"`, the bound state
must expose applicable HA `unit_of_measurement` equal to `source_unit` at
staging and at every valid read; `Sensor.unit` must equal it. Missing or
changed live unit makes the reading `available=False`, `confidence=None`
and raises the drift diagnostic. With
`source_unit_authority="declared_attribute_contract"`, only an explicit
`AttributeReadBinding` may use the developer-declared attribute source unit;
the enclosing entity's unrelated unit metadata is never treated as that
attribute's unit. Staging fingerprints the attribute path and declared unit;
changing either requires a new generation. Runtime still rejects invalid,
non-finite raw or converted numbers. No automatic conversion is selected
solely because a new HA unit string happens to match another registered
converter; that change needs staging under a new source-unit contract.

### 3.4 HA-assisted environmental discovery — staging only

Home Assistant metadata can make registration faster, but cannot establish house semantics. During
configuration staging, the adapter may inspect the already-present HA state object and emit an
ephemeral `EnvironmentalDiscoveryCandidate`:

```python
@dataclass(frozen=True)
class EnvironmentalDiscoveryCandidate:
    entity_id: str
    read_path: ReadBinding
    domain: str
    device_class: str | None
    state_class: str | None
    unit: str | None
    device_id: str | None
    suggested_location: Location | None
    suggested_slot: str | None
    confidence: Literal["auto_compatible", "review_required"]
    required_admin_decisions: tuple[str, ...]
```

The candidate is an admin-facing staging aid, not a `Sensor`, a persisted raw HA payload, or a
runtime data path. Accepting it creates an ordinary explicit `Sensor` with a concrete binding,
`fact_type`, `Interpretation`, source-shape expectation, and any required topology relationship;
declining it leaves the generation unchanged. Discovery performs no network call, service call, or
continuous scan in Layer 2's cycle path.

`auto_compatible` means only that HA exposes a physically shaped reading whose device class, state
class, and unit are compatible with an unambiguous *candidate slot*: temperature, relative or absolute
humidity, pressure, carbon dioxide, illuminance, irradiance, PM2.5, wind, or precipitation. It may
prefill the binding and source-shape expectation, but the admin still assigns the indoor/outdoor and
room/exterior meaning and accepts the registration. `review_required` covers readings for which HA's
metadata does not determine Heima semantics: window/contact and cover state, weather and climate
attributes, AQI, and existing HA binary/threshold helpers. A weather entity yields one candidate per
usable attribute through `AttributeReadBinding`, never one opaque "weather sensor". For a helper,
Heima preserves HA's established threshold logic and offers its output only as a guard source; it does
not recreate the threshold from raw measurements.

Discovery must never infer indoor versus outdoor placement, an opening relationship, comfort or
safety thresholds, security/privacy meaning, occupancy meaning, an acceptable outdoor-air condition,
or an automation policy. In particular an AQI/device-class label is not equivalent to the normalized
`outdoor_air_quality` guard required by Layer 3: the explicit Sensor/Interpretation or a dedicated
Layer 2 normalizer must state its scale and acceptable condition. Area and device-registry information
may suggest a location, but remain `required_admin_decisions`; only the accepted generation records
the resulting meaning.

This deliberately follows HA's entity metadata model rather than recreating a parallel taxonomy:
`device_class`, unit, and `state_class` identify the physical shape and statistics of a sensor value,
while weather integrations expose several values as entity attributes. See Home Assistant's
[sensor entity contract](https://developers.home-assistant.io/docs/core/entity/sensor/) and
[weather entity contract](https://developers.home-assistant.io/docs/core/entity/weather/). Those
contracts justify a candidate and validation aid, not an inference of a home's physical or policy
semantics.

### 3.5 Desktop-workstation normalization and privacy

A desktop client is an ordinary `Sensor` source, never a parallel computer-telemetry subsystem. The
official macOS Companion App can expose active use, frontmost application, microphone/camera use, and
device location capability; third-party desktop agents may expose comparable platform-specific paths.
Layer 2 accepts only explicit, per-Sensor opt-in registrations and normalizes them into bounded facts
such as `computer.interaction_active`, `computer.work_application_active`,
`computer.communication_application_active`, `computer.audio_video_input_active`, and
`computer.session_locked`. A static workstation's `where` is an administrator-declared room; a mobile
laptop's geographic/device location does not imply a room location without a separately declared local
binding.

No raw window title, document name, URL, meeting subject, participant, audio/video content, screen
image, keystroke, or unclassified application name becomes a `HouseFact`, formula input, learning
feature, or persisted Heima payload. Where an integration exposes the foreground application, its
binding maps it locally through an explicit reviewed category to one boolean normalized fact; the raw
value remains only in Home Assistant's source state. `computer.communication_application_active` plus
microphone/camera use may support a later deterministic `communication_session_active` fusion, but is
not itself proof of a call and never proof of work. A computer being active, unlocked, or in one room
does not itself prove that a resident is working.

This is deliberately capability- and privacy-based rather than integration-name-based: the source may
be replaced without changing a logical Sensor id or its normalized fact semantics. The administrator
must opt in separately to interaction, application-category, microphone/camera, and location paths;
there is no desktop telemetry default. These normalized facts can be current Layer-2 inputs to a
working-context contract, while a direct Layer-5 interruption policy may independently consume a
declared communication-session fact without waiting for learning.

### 3.6 Core solar-geometry bindings

Initial V3 obtains solar position through the existing Layer-2 `Sensor`
mechanism. When a staged environmental formula or learning definition needs
solar geometry, the core contributes exactly two reserved, casa-scoped Sensor
registrations: `solar_elevation` claims `external.solar_elevation` and
`solar_azimuth` claims `external.solar_azimuth`. Their respective
`AttributeReadBinding`s read `sun.sun` attributes `elevation` and `azimuth`
from the **same frozen HA state snapshot**. The Home Assistant Sun integration
publishes those attributes in degrees with azimuth clockwise from north
([Sun integration](https://www.home-assistant.io/integrations/sun/)); it is
the input source, not a second Heima solar-position calculation.

Both registrations use `NumericInterpretation`,
`QuantitativeUnitContract(source_unit="deg", canonical_unit="rad",
source_unit_authority="declared_attribute_contract",
conversion_ref=UnitConversionRef("angle.degrees_to_radians.v1", "1"))`,
`reliability=1.0`, and `max_source_age=Window(seconds=1800)`.
The frozen core converter is the pure finite `degrees * π / 180` operation;
its id/version and exact unit pair are registered under §3.3. The converted
elevation is bounded inclusively by `[-π/2, π/2]`, the clockwise-from-north
azimuth by `[0, 2π]`; `2π` is the same north bearing as zero for the
downstream cosine. These are `numeric_bounds` on the two Sensor registrations.
The 30-minute source-age limit permits the Sun integration's documented
day/night update cadence while preventing an old HA value from masquerading
as current geometry ([core Sun entity implementation](https://github.com/home-assistant/core/blob/dev/homeassistant/components/sun/entity.py)).

The two core-generated Sensors contribute the exact exclusive state
`FactTypeClaim`s through Layer 0's normal claim collision check. No administrator Sensor,
plugin or formula may publish either claim concurrently, and another Sensor
cannot register either reserved `sun.sun` attribute path under a second fact
type because one HA readable signal path has one registered owner. Both facts carry
ordinary Layer-2 `FactSource` identity and the canonical radian unit; neither
contains raw HA attributes. A missing, unavailable, stale, nonnumeric or
out-of-range source makes the affected fact `available=False`; the
solar-incidence formula needs both available facts and therefore abstains if
either fails. Startup never reuses a pre-restart solar reading. The staged
source entity/attribute paths, converter version, bounds, age limit and HA
observer-location fingerprint enter the two Sensor execution fingerprints.
A changed HA home location is a staged source-definition update, as are a
source binding or converter version change. Until that new generation is
committed, solar geometry is unavailable; the ordinary selective generation
revalidation then invalidates dependent solar
formula plans and learning artifacts; evaluation never queries HA location
or calculates an ephemeris on the policy path. Installations without a
usable Sun source may keep unrelated automations active, while a solar
dependent plan remains unavailable until fresh geometry arrives.

---

## 4. `Interpretation` — how raw binding input becomes a `HouseFact` value

```python
@dataclass(frozen=True)
class NoDefault:
    pass

NO_DEFAULT = NoDefault()
MappingDefault = EvidenceValue | NoDefault

@dataclass(frozen=True)
class MappingInterpretation:
    mapping: dict[str, EvidenceValue]   # raw string input -> normalized HouseFact.value, exact match.
                                          # Value type is EvidenceValue (Layer 1 §3/§4 — the same
                                          # shape constraint HouseFact.value itself already carries),
                                          # not Any.
    default: MappingDefault = NO_DEFAULT
    # default=<value>: a raw string absent from `mapping` produces this value instead — always
    #   available=True once the binding succeeds (§3.2). This is how a boolean-style sensor
    #   ({"on": True, "charging": True, "full": True}, default=False), a presence sensor
    #   ({"home": True}, default=False), or a media-activity sensor ({"playing": "playing",
    #   "paused": "paused", "buffering": "buffering"}, default="idle") are expressed — the same
    #   exact-match-lookup mechanism, a configurable vocabulary instead of a hardcoded one per HA
    #   domain (resolved 2026-09-05, see below).
    #   `None` is a valid EvidenceValue, so default=None means the produced HouseFact.value is really
    #   None with available=True.
    # default=NO_DEFAULT: a raw string absent from `mapping` means "no interpretable value" —
    #   available=False (§3.2), the same mechanism CalendarInterpretation's own "no match" uses,
    #   generalized to any discrete vocabulary, not just calendar keywords.

@dataclass(frozen=True)
class NumericInterpretation:
    pass
    # A valid finite numeric input is first converted through the Sensor's staged
    # QuantitativeUnitContract, then becomes its canonical-unit float value.
    # There is no implicit range policy, rounding, or fallback here.

@dataclass(frozen=True)
class Bucket:
    label: str
    upper_bound: float | None   # None = open-ended top bucket

@dataclass(frozen=True)
class BucketInterpretation:
    buckets: tuple[Bucket, ...]         # ordered lowest to highest, e.g. dark/dim/ok/bright — at
                                          # least one entry; the ordered chain of upper_bounds plus
                                          # the open-ended top bucket makes this total over the
                                          # entire real line by construction, given a non-empty tuple;
                                          # thresholds use the Sensor contract's canonical unit

@dataclass(frozen=True)
class KeywordClassifier:
    keywords: dict[str, list[str]]      # category -> matching keywords
    priority_order: list[str]           # tie-break order when multiple categories match
    # Pure classifier: it accepts a finite sequence of strings and returns one configured category or
    # None. It owns normalization, matching, and deterministic priority; it performs no I/O and has
    # no calendar-time semantics.

@dataclass(frozen=True)
class CalendarInterpretation:
    classifier: KeywordClassifier
    # Calendar-specific wrapper: aggregates the summaries of active_now windows, then delegates their
    # classification to classifier. It works with any calendar.* backing; source choice is not model.

Interpretation = (
    MappingInterpretation | NumericInterpretation | BucketInterpretation | CalendarInterpretation
)
```

**Binding-input contract is exact and checked before cycles.** `StateReadBinding` supplies its valid
raw HA state string; `AttributeReadBinding` supplies its valid raw attribute value; either may feed
only `MappingInterpretation`, `NumericInterpretation`, or `BucketInterpretation`. Mapping is an exact
string lookup: an attribute value must therefore already be a `str`, with no `str(...)` conversion.
Numeric and bucket interpretations share one strict numeric parser: accept a non-boolean `int` or
finite `float`, or an ASCII decimal string whose entire content matches the regex
`[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?`; normalize it to a finite `float`.
Whitespace, locale formatting, booleans, `NaN`, infinity, malformed strings, and every other value are
type failures, producing `available=False`/`confidence=None` and a diagnostic. They never throw into
the cycle, silently coerce, convert units, or select a bucket. `CalendarWindowReadBinding` supplies
only `active_now` windows and pairs exclusively with `CalendarInterpretation`; the reverse pairing is
also exclusive. All of these compatibility and configuration checks occur during candidate-generation
staging, never as a runtime guess.

**Keyword classification is defined once; calendar use is only one wrapper.** `KeywordClassifier`
applies Unicode NFKC normalization, `casefold()`, and whitespace collapsing to temporary copies of
each supplied text and configured keyword. A keyword matches when its normalized text is a substring
of the normalized input. It gathers every matching category across the supplied texts, then returns the
category occurring earliest in `priority_order`, or `None`. Registration rejects a `priority_order`
that does not list every key in `keywords` exactly once and no other category, any category with an
empty keyword list, or any individual keyword whose normalized text is empty. This includes an empty
or whitespace-only keyword beside valid keywords; no empty substring reaches matching.
`CalendarInterpretation` passes only the raw summaries of its active
windows to that classifier; stored `CalendarWindow.summary` remains unmodified. Thus overlap within one
calendar is deterministic without Layer 0 assigning a category. `None` means this Sensor has no signal
(`available=False`). Conflicts between separate `calendar.*` entities remain explicit consumer policy.

This closed union has four genuinely distinct decoding **mechanisms**: exact finite-vocabulary lookup
(`MappingInterpretation`), strict continuous numeric normalization (`NumericInterpretation`), numeric
range membership (`BucketInterpretation`), and calendar-window aggregation plus keyword classification
(`CalendarInterpretation`). **Resolved 2026-09-05** (`v3_backlog.md`): this union previously carried five members
(`BooleanInterpretation`, `MediaActivityInterpretation`, `PresenceInterpretation` alongside these
three); three of those were the exact same exact-match-lookup mechanism, each hardcoding its own
vocabulary instead of taking one as configuration. Collapsed into `MappingInterpretation`'s
`mapping`/`default`, with `NO_DEFAULT` as the explicit "no fallback value" sentinel, which also
extends for free to any future closed-discrete-vocabulary HA domain
(a lock, an alarm panel, a vacuum, `climate.hvac_action`...) without ever reopening this union for
that pattern again. A future variant is added the same deliberate way `FusionStrategy` gained
`FormulaStrategy` (§5.1) — only when a genuinely distinct decoding **mechanism** is found, never for
one sensor's convenience, which is exactly the discipline this collapse restores after
`MediaActivityInterpretation` had quietly drifted from it.

**`NO_DEFAULT`, not `None`, means "no fallback" — resolved 2026-09-08.** Layer 1's `EvidenceValue`
explicitly includes `None`, so `MappingInterpretation(default=None)` must remain available as a real,
intentional output value (`HouseFact.value is None`, `available=True`) rather than being overloaded to
mean "no interpretable value." The in-memory sentinel is the frozen dataclass singleton
`NoDefault()`/`NO_DEFAULT` above; in configuration/storage, the preferred representation is that the
`default` field is absent. If the field is present with JSON `null`, that is the real `None` value,
not the sentinel. This makes total vs. partial mappings mechanically distinguishable in tests and in
admin-authored config.

**Physical room occupancy vs. whole-house presence — independently tuned, never a shared timing policy.**
Layer 2 consumes the per-sensor evidence namespace above and produces `occupancy.physical` through
its own `FusionRule`; Layer 4 resolves the canonical semantic `occupancy` from that conclusion and
an optional authorized indirect hint. Layer 2 similarly produces `presence.physical` from only declared
casa-presence evidence; Layer 4 resolves the semantic `presence` claim. Physical occupancy and physical
presence each carry their own strategy and `stability` (§5.2) — physical room occupancy keeps a
fast-on/slow-off default (`Stability(to_true=None, to_false=Window(seconds=120))`), while
whole-house presence can use a more conservative pair. They run independently per cycle; sharing
evidence vocabulary never shares a blocking path or timing policy.

---

## 5. `FusionRule` — how N facts become one derived `HouseFact`

**Genuinely separate from `Sensor`, not folded into it** — not every `Sensor` needs fusing (a
context-recording sensor can stand alone with no `FusionRule` referencing it), and not every fusion
has the same shape.

```python
@dataclass(frozen=True)
class FactRef:
    fact_type: str   # Layer 1 §3 naming convention
    where: Location  # Layer 1 §5
    previous_cycle: bool = False
    # Identifies "the HouseFact for this fact_type at this Location" — the same address every other
    # consumer in this architecture already queries by (Layer 0: "every HouseFact true in Location X"
    # is the generic query shape). A FusionRule's inputs are addressed this way, not by producer id,
    # specifically so it never needs to know or care whether a given input came from a Sensor or from
    # another FusionRule — see §5.6.
    #
    # This type addresses state facts only; a FactTypeClaim with emission_kind="event" is rejected at
    # registration because an event has no current value to address.
    #
    # `previous_cycle` defaults to False: current-cycle value in §5.6's topological order. True means
    # the value at the end of the previous completed cycle, read from Layer 0's sealed in-memory
    # PreviousCycleSnapshot. Staging accepts True only on a FormulaStrategy input whose fact_type and
    # where exactly equal its owning FusionRule's produces/where, and only when that core formula's
    # validate_binding explicitly permits it (§5.8). It is therefore explicit self-memory, never a
    # generic one-cycle edge to another producer. After restart, Layer 0 pre-hydrates only after a
    # clean shutdown; an unclean first cycle yields available=False.

@dataclass(frozen=True)
class FusionRule:
    fusion_id: str
    inputs: tuple[FactRef, ...]    # order matters for PrecedenceStrategy, irrelevant otherwise
    strategy: FusionStrategy
    produces: str                  # fact_type of the derived HouseFact
    where: Location                 # the derived fact's own "destination location" — its
                                     # relationship to inputs' own "source locations" is
                                     # strategy-specific, not universal — §5.7
    stability: Window | Stability | None = None  # §5.2 — debounce/hysteresis on the *output*,
                                                   # applies regardless of which strategy produced
                                                   # it; not part of FusionStrategy itself
```

### 5.1 The five strategies

```python
@dataclass(frozen=True)
class DirectStrategy:
    pass   # 1:1 passthrough — relabels its one input's fact under a new fact_type; value and
           # location unchanged. Exactly one FusionRule.inputs entry, always (§5.7).

@dataclass(frozen=True)
class UnanimityStrategy:
    min_available: int
    # True only if every currently-available boolean input is True — resolved 2026-09-08, renamed and narrowed
    # from the earlier BooleanSetStrategy(mode: Literal["any", "all"]). "any" was found to be a pure
    # redundancy: WeightedQuorumStrategy(weight=1 for every input, threshold=1.0) produces the exact
    # same outcome in every availability scenario, since "at least one" never needs its bar to scale
    # with population size (see WeightedQuorumStrategy's own comment below). "all" (unanimity) could
    # *not* be expressed the same way: it requires the bar itself to track total_weight_considered,
    # which changes every cycle as inputs become available/unavailable (§5.5) — a fixed
    # WeightedQuorumStrategy.threshold cannot do this (one sensor going offline would make a fixed
    # numeric threshold permanently unreachable, even though every remaining input still agrees). This
    # is the one genuine case a linear weighted threshold cannot express, which is what still justifies
    # a separate strategy for it, renamed here to say plainly what it does now that it does only one
    # thing.
    #
    # min_available: mandatory floor on how many configured inputs must be available before this
    # strategy reports anything at all — see §5.5. A strict all-configured-input policy is expressed
    # explicitly as len(inputs); a smaller value is an explicit partial-availability policy. There is
    # no default that lets one surviving input silently speak for the rest.

@dataclass(frozen=True)
class WeightedQuorumStrategy:
    weights: dict[FactRef, float] = field(default_factory=dict)
    # Resolved 2026-09-05: a sparse override, not a second membership list. `FusionRule.inputs` (§5)
    # is the single source of truth for which inputs feed this strategy, for all five strategies
    # without exception — `weights` only overrides the default weight (1.0) for entries that need a
    # non-default one. A key in `weights` that is not also in the owning `FusionRule.inputs` is a
    # registration-time error, same discipline as §2.3's producer-uniqueness check; most
    # configurations need no entries here at all.
    threshold: float = 1.0
    min_available_weight: float = 0.0
    # a floor on total available weight (not configured weight) before this strategy reports
    # anything at all — see §5.5. Default 0.0 restates the general "empty population ->
    # available=False" rule with no extra requirement; a nonzero value is how a producer declares
    # "I don't trust a result computed from only a small fraction of my configured sensors" —
    # exactly the min_support-style completeness gate, kept separate from confidence itself
    # (Layer 1 §4.2), not blended into it.
    # a plain count-threshold ("at least N active") is this strategy with every weight = 1 — not a
    # separate strategy; "at least one active" ("any") is the same idiom at N=1 (weight=1 for every
    # input, threshold=1.0) — resolved 2026-09-08, this is why `UnanimityStrategy` above dropped its
    # own "any" mode instead of keeping two ways to say the same thing.
    #
    # Does *not* incorporate each input's own confidence/reliability into winning_weight/
    # total_weight_considered, by design, not by omission (resolved 2026-09-07): `weight` is already
    # the lever for "how much should this input count," declared once by whoever registers it — folding
    # a second, independent signal (a Sensor's own `reliability`, §3.2) into the same computation would
    # let it silently override the configured weight's own meaning (e.g. a low-reliability input could
    # flip the reached/not-reached outcome even though its weight said it should count fully), and
    # would duplicate a control the producer already has direct, explicit access to: register that
    # input with a lower `weight` instead. `UnanimityStrategy` (above) is the opposite case: it has no
    # `weight` field at all, so `combined_confidence` over each input's own confidence (§5.4) is its
    # *only* available way to express "trust this input less" — `WeightedQuorumStrategy` already has
    # that lever, so it doesn't need a second one.

@dataclass(frozen=True)
class PrecedenceStrategy:
    pass   # tries inputs in order, first Fact with a definitive (available) value wins — e.g.
           # a semantic resolver's own top-level resolution order, one layer up (§5.1 continued below for
           # workday_entity, which needs care not to be misread as a flat 5-way chain)

@dataclass(frozen=True)
class PhysicalEvidenceBinding:
    input_index: int
    role: Literal["primary", "supporting"]
    true_weight: float
    false_weight: float
    required_for_false: bool

@dataclass(frozen=True)
class CompiledFormulaConfiguration:
    pass  # immutable core-internal object; never serialized or accepted from admin configuration

@dataclass(frozen=True)
class NoFormulaConfiguration(CompiledFormulaConfiguration):
    pass

@dataclass(frozen=True)
class PhysicalEvidenceWeightedConfig(CompiledFormulaConfiguration):
    bindings: tuple[PhysicalEvidenceBinding, ...]
    true_threshold: float
    false_threshold: float

@dataclass(frozen=True)
class ResolvedPhysicalEvidenceBinding:
    binding: PhysicalEvidenceBinding
    admission: PhysicalEvidenceAdmission  # resolved from the staged Sensor, never repeated in JSON
    correlation_group: str                # resolved from the staged Sensor, never an HA entity id

@dataclass(frozen=True)
class ResolvedPhysicalEvidencePlan(CompiledFormulaConfiguration):
    bindings: tuple[ResolvedPhysicalEvidenceBinding, ...]
    true_threshold: float
    false_threshold: float

JsonScalar = str | int | float | bool | None
JsonValue = JsonScalar | tuple["JsonValue", ...] | Mapping[str, "JsonValue"]
FormulaConfigurationPayload = Mapping[str, JsonValue] | None

@dataclass(frozen=True)
class FormulaStrategy:
    formula_id: str
    configuration: FormulaConfigurationPayload = None  # canonical JSON object, compiled at staging (§5.3)
    # Closes the "genuine calculation" gap the other four don't cover (Heating's Season derived from
    # outdoor_temp with hysteresis; a future "effective outdoor temperature" from temp+wind+humidity)
    # — carries no calculation logic itself, only a reference into a separate, core-team-curated
    # formula registry (§5.3), plus that formula's canonical JSON configuration payload where one is
    # required. Its declared confidence mode determines the output/result contract, so a new formula
    # never requires reopening a configuration union or any code that pattern-matches on it.
    # Resolved 2026-09-02, v3_backlog.md, closing AR-4.

FusionStrategy = (
    DirectStrategy | UnanimityStrategy | WeightedQuorumStrategy | PrecedenceStrategy | FormulaStrategy
)
```

**Boolean vote contract — resolved 2026-09-08.** `UnanimityStrategy` and
`WeightedQuorumStrategy` are boolean strategies: every `available=True` input they consider must have
an exact `bool` value. `True` is the sole vote "for"; `False` is the sole vote "against". This is
an exact-type rule, not language truthiness: `0`, `1`, `"on"`, `"off"`, `None`, and every structured
`EvidenceValue` are invalid votes even where a host language would coerce one of them to boolean.
Both strategies always produce a boolean value when they produce a value at all.

An `available=True` input whose value is not an exact `bool` is a configuration/type mismatch at
evaluation time. The fusion produces `available=False`/`confidence=None` for that cycle and raises a
Layer 0 §10 diagnostic identifying the fusion and offending `FactRef`. It is deliberately not
coerced to `False` and not silently excluded: either would convert an invalid producer contract into
a plausible but wrong vote. This check is necessarily at evaluation time because `FactRef` addresses
the generic `HouseFact` contract, whose value shape can depend on the source's current interpretation
or an upstream formula; registration still catches every structural invariant it can know statically.

A closed union of five — not an open-ended plugin registry (an earlier draft of the architecture
recap described it as one; corrected, `v3_backlog.md`, AR-4 follow-up). Exhaustive pattern-matching
on `FusionStrategy` is a real property every consumer can rely on; the one extension point is
`FormulaStrategy`'s own registry (§5.3), not the union itself.

**`workday_entity`, worked through precisely — two mechanisms at two levels, not one flat chain.**
The recurring shorthand for this case ("office > day_off > holiday > wfh > raw entity") reads like a
single 5-way `PrecedenceStrategy` and is easy to misimplement as one. It isn't:
`CalendarInterpretation` (§4) composes one `KeywordClassifier` — multiple categories handled by **one**
`Sensor`, with that classifier's `priority_order` breaking ties when one event's text matches more than
one category's keywords. `PrecedenceStrategy` solves a different problem — falling back to a different
*Sensor* when one has nothing to say — not classifying ambiguity within one. The correct shape is
**one** `Sensor` with a `CalendarInterpretation(classifier=KeywordClassifier(...))` whose classifier
resolves office/day_off/holiday/wfh internally, and **one**
`FusionRule(strategy=PrecedenceStrategy())` with
exactly two `inputs`: that calendar-derived `Sensor`'s `FactRef`, then the raw `workday_entity`
`Sensor`'s `FactRef` as the fallback when the calendar `Sensor` produces no match (`available=False`)
at all. Four Sensors feeding a flat 5-item precedence chain would work mechanically too, but would leave
the calendar classifier's `priority_order` doing nothing for this case — a sign the modeling is wrong,
not just a stylistic choice between two equally-valid shapes.

### 5.2 Stability is orthogonal to strategy

Dwell/hysteresis (`FusionRule.stability`) applies to the **output**'s stability over time,
independent of which strategy produced it — debounce and hysteresis are a property of *any* derived
fact settling before it's trusted, not specific to one combination method. It composes with all five
strategies identically; `FusionStrategy` itself carries no timing concept.

**Asymmetric by default need, not just by option — a single `Window` cannot express "instant on,
debounced off."** A room's light triggered by presence must turn on the instant presence is
detected, never after a dwell delay (the room would sit dark for no reason); the same fact should
often *not* revert to vacant on the first gap in motion, to avoid flicker from an ordinary pause.
This asymmetry is already real and working in today's code (`on_dwell_s=0`, `off_dwell_s=120s` for
room occupancy) — a single symmetric `stability: Window` would either delay the light turning on
(reintroducing exactly the problem it must not have) or drop hysteresis on the off-transition
entirely. For strategies with a natural true/false polarity (`UnanimityStrategy`,
`WeightedQuorumStrategy` used with a boolean threshold):

```python
@dataclass(frozen=True)
class Stability:
    to_true: Window | None = None    # e.g. None — a presence-triggered light turns on instantly
    to_false: Window | None = None   # e.g. Window(seconds=120) — debounce the off-transition
    unavailable_grace: Window | None = None
                                      # None: emit unavailable immediately. Otherwise, retain the last
                                      # committed available output only for this bounded interval when
                                      # the candidate becomes unavailable; never completes an old dwell.
```

`FusionRule.stability: Window | Stability | None` — a plain `Window` (or `None`, no dwell at all)
still covers strategies without a boolean polarity (`FormulaStrategy`'s numeric output settling,
`DirectStrategy`/`PrecedenceStrategy` passing through a non-boolean value) with symmetric dwell in
both directions; `Stability` is available specifically where "toward more active" and "toward less
active" are genuinely different questions. Not generalized further (e.g. per-transition dwell across
an N-valued bucket label) — no concrete need for that exists today; the same discipline already
applied to `FusionStrategy`'s own five members, add complexity when a real case demands it, not ahead
of one.

`unavailable_grace` is intentionally available only on `Stability`, where the output has boolean
polarity and a resident-visible continuity benefit has been established. Its default is `None`: no
grace, immediate unavailable. A rule that needs it opts in with a positive `Window` (room occupancy
may begin with `30s`); a security-critical rule leaves it unset. A plain symmetric `Window` has no
availability grace.

**The mechanism, concretely — not just "debounce happens," but how.** Every cycle, a `FusionRule`
computes its raw candidate from its current `inputs` per its strategy, exactly as if
`stability` were absent. Value dwell compares only two **available** values;
publication compares the candidate's complete Layer-0
`FactChangeFingerprint` with the last derived `HouseFact` this `FusionRule`
actually committed. An unavailable fact has no value to compare:

The associated control state is a Layer-2-owned, O(1)-indexed `FusionRuleRuntimeState` keyed by
`fusion_id`: pending value/since/due, availability-grace since/due, and the generation/token of each
armed deadline. It is ephemeral and never enters Layer 0's short-term history buffer, Persistence, or
a checkpoint. Layer 0 owns only the corresponding `AtJob`; its callback returns to the Layer-2
evaluator with the token so a superseded deadline cannot commit stale state. This preserves a strict
boundary: the Layer-0 buffer answers historical `Window` queries over `HouseFact`s, while Layer 2
owns its own per-fusion control state. Restart and impacted registry reload discard this state; the
latter does so only for its §2.5 impact set.

- If the raw candidate is `available=False`, first cancel any pending `to_true`/`to_false` transition:
  that transition was supported by evidence no longer available and must never commit later. When
  `unavailable_grace` is configured and the last committed output is available, start or continue one
  ephemeral availability-grace record `(last_committed_output, unavailable_since, due)` and arm one
  Layer-0 `AtJob` for `due`. During this interval the committed output remains the rule's deliberate
  temporal result; no per-cycle fact write occurs. If a fresh available candidate arrives first,
  cancel the job and grace record, then process that candidate under the ordinary rules below. If the
  job reaches `due` while the candidate is still unavailable, commit exactly one
  `available=False`/`confidence=None` fact and clear the grace record. With no grace, or no prior
  available committed output, commit that unavailable fact immediately. Grace records are ephemeral:
  reload impact invalidation and every restart cancel them rather than extending stale output.

- If the candidate and last committed output are both available and their
  values match, cancel any pending directional transition and invalidate its
  deadline token. Returning to the committed value withdraws the candidate
  that justified the dwell. Then compare their complete
  `FactChangeFingerprint`s: if confidence or stable source/route changed,
  commit the current candidate in this cycle without a new value dwell;
  otherwise emit no new fact. A callback already queued with the old token is
  harmless. If the last committed output is unavailable, do not compare its
  undefined value: the available candidate follows its ordinary directional
  window below, including a fresh dwell where configured.

For an available candidate, determine its applicable directional window *before* creating pending
state. The two cases are deliberately different:

- **No dwell (`None`) is a same-cycle fast path.** If the available candidate differs from the last
  available committed value, or reacquires availability, and its applicable window is `None`
  (including `FusionRule.stability=None`), cancel any stale
  pending deadline and commit it in this same evaluation. `None` means no required stability time, not
  "wait until a later evaluation". This is what makes `Stability(to_true=None, ... )` genuinely
  instant-on for occupancy/presence and avoids an artificial extra-cycle latency.
- **A positive dwell is one verified deadline, not polling.** Dwell and grace deadlines use
  Layer-0 `AtJob.basis="elapsed"`. If the candidate differs and its window
  is positive, replace any pending transition toward another value, record
  `(pending_value, pending_since, due=pending_since+window, token, generation)`, and arm exactly one
  Layer-0 `AtJob` for `due`. A subsequent input-driven evaluation that still sees that same candidate
  retains the existing deadline; it never extends the dwell merely because another cycle occurred. If
  it instead sees the committed value, a different candidate, or unavailability, it cancels the
  deadline and discards or replaces the pending transition as applicable.

At its deadline, a dwell `AtJob` triggers a generation- and token-checked, targeted evaluation of that
fusion and its current-cycle dependents against the latest in-memory input facts. It performs no HA,
network, or Persistence read and never commits the candidate captured at arm time blindly. Only if the
freshly recomputed candidate is still available, equal to `pending_value`, and the token/generation
still match may it commit the fresh complete value/confidence/source route and clear pending state.
An epistemic change while the same value is pending does not restart its
dwell; the deadline publishes the then-current fingerprint. Thus the transition
occurs as soon as the configured dwell elapses even without an unrelated HA event or periodic fallback,
while a stale callback cannot write a value that later evidence has withdrawn. Pending state is
ephemeral and deliberately not restart-safe: a fresh restart begins a full dwell period before any
positive-dwell transition can commit, consistent with Recovery's `startup_recovery` caution (Layer 0
§7).

The diagnostic surface exposes every pending dwell and active availability grace with fusion id, due
instant, token/generation, retained or pending value, and unavailable `FactRef`s where applicable.
Entering, replacing, cancelling, and expiring either state are diagnostic transitions, not per-cycle
durable event facts; each uses at most one deadline `AtJob`, avoids polling, and keeps the hot path
constant-time.

### 5.3 The formula registry

```python
FormulaId = str   # e.g. "heating.season_hysteresis", "external.effective_outdoor_temperature",
                   # "physical_evidence.weighted_evidence"
FormulaImplementationVersion = str  # non-empty, core-maintained semantic implementation version
FormulaConfidenceMode = Literal["continuous", "categorical", "inherit_input"]

@dataclass(frozen=True)
class ContinuousFormulaResult:
    value: float
    dispersion: float

@dataclass(frozen=True)
class CategoricalFormulaResult:
    value: EvidenceValue
    support: float
    total: float

@dataclass(frozen=True)
class InheritedFormulaResult:
    value: EvidenceValue
    confidence_input_index: int  # zero-based index into the configured input sequence; selected fact
                                 # must itself be available

FormulaResult = ContinuousFormulaResult | CategoricalFormulaResult | InheritedFormulaResult
FormulaConfigurationCompiler = Callable[[FormulaConfigurationPayload], CompiledFormulaConfiguration]
FormulaBindingValidator = Callable[["FusionRule", FormulaStrategy, CompiledFormulaConfiguration], CompiledFormulaConfiguration]

@dataclass(frozen=True)
class RegisteredFormula:
    formula_id: FormulaId
    implementation_version: FormulaImplementationVersion
    min_inputs: int                                                     # formula-specific — Season's
                                                                          # hysteresis needs 1, an
                                                                          # "effective temperature"
                                                                          # might need 2 of 3
    confidence_mode: FormulaConfidenceMode
    compile_configuration: FormulaConfigurationCompiler  # pure staging-time JSON decoder/validator
    validate_binding: FormulaBindingValidator  # pure staging-time check of inputs, order, output,
                                               # previous_cycle use; returns immutable resolved plan
    compute: Callable[[Sequence[HouseFact], CompiledFormulaConfiguration], FormulaResult | None]
                                                                    # receives every configured input in
                                                                    # FusionRule.inputs order, including
                                                                    # available=False facts, and only the
                                                                    # registered formula's staging-compiled config
    scale: float | None = None  # required only for confidence_mode="continuous"
    floor: float | None = None  # required only for confidence_mode="continuous"
```

The **Formula Registry** is a core-owned immutable catalog, constructed once during integration
bootstrap before any `RegistryGeneration` is staged. Core modules call `register(RegisteredFormula)`
only while this catalog is being built; duplicate `formula_id`, an empty version, or a registration
after `freeze()` aborts startup. `freeze()` exposes an immutable `formula_id -> RegisteredFormula`
map; `resolve(formula_id)` is O(1), has no I/O, lock acquisition, dynamic import, or plugin callback,
and is the only lookup the evaluator performs. There is no admin, service, or third-party registration
surface.

`implementation_version` is an explicit semantic version maintained with the core formula. Any change
that can alter configuration compilation, `compute`, or binding-validation behavior must bump it;
cosmetic/internal changes that cannot alter any of those need not. The compiler, callable, and validator
are runtime code and are never serialized. The candidate `RegistryGeneration` stores only the resolved
`formula_id`, `implementation_version`, and canonical configuration JSON alongside the `FusionRule`
definition; its active in-memory plan additionally holds the formula's validated, resolved compiled
configuration. On
startup after a code upgrade, staging compares that resolved pair and payload with the active generation:
a difference follows §2.5's selective impact path, never a live replacement of a formula during a cycle.

`FormulaStrategy.configuration` is either `None` or a canonical JSON object under Layer 1's shared
RFC-8785 rule: string keys are unique and sorted as raw UTF-16 code-unit sequences; arrays preserve
their declared order; numbers are finite; nesting is at most 8; and the UTF-8 serialization is at most
16 KiB. It is configuration data, not Layer 1 `EvidenceValue`: formula
configuration may legitimately contain an ordered array of binding objects. During staging, after
`resolve`, the registry first calls the formula's pure `compile_configuration(payload)`, then passes its
immutable result to `validate_binding(fusion_rule, formula_strategy, compiled_configuration)`. The
validator returns the final immutable plan held by the active generation; an ordinary formula returns
its input unchanged, while a formula that must resolve staged input metadata may enrich it there.
Together they must reject every semantic mismatch knowable before evaluation: JSON shape/fields/values,
input count/order and fact-type contract, output `produces`/`where`, and every `previous_cycle` input
unless it exactly self-references that FusionRule and this formula explicitly permits its
position/count, plus the formula's exact compiled configuration type. Neither may read HA,
Persistence, or mutable runtime state. A failed compiler or validator rejects the whole candidate
generation; parsing is never deferred to a diagnostic from `compute` on a resident-facing cycle, and
`compute` never parses JSON.

**Formula result and confidence contract — resolved 2026-09-08.** `confidence_mode` is declared by
the core-team-owned registry entry, never inferred from a formula's name or its incidental Python
return type:

- `continuous` requires a `ContinuousFormulaResult`: `value` is a finite numeric measurement (a
  `float`, never `bool`) and `dispersion` is its non-negative spread. The entry must supply
  `scale`/`floor`, and its confidence is `continuous_confidence(dispersion, scale, floor)`.
- `categorical` requires a `CategoricalFormulaResult`: `value` is any `EvidenceValue`; `support` and
  `total` are the formula's explicitly defined evidence population for the reported category. Its
  confidence is `categorical_confidence(support, total)`, so `total > 0` and
  `0 <= support <= total` are mandatory.
- `inherit_input` requires an `InheritedFormulaResult`: `confidence_input_index` is a zero-based
  index into the configured `FusionRule.inputs` sequence passed to `compute`; the referenced fact
  must be `available=True`, and the result inherits that fact's confidence unchanged. This is for
  deterministic transforms/classifications with no honest
  dispersion or support population to manufacture, such as `heating.season_hysteresis` derived from
  a temperature input.

`scale` and `floor` are required for `continuous` and prohibited for the other two modes. A result
whose variant does not match `confidence_mode`, an out-of-range categorical population, a non-finite
continuous value/dispersion, or an invalid inherited-input index is a formula-contract violation: the
fusion returns `available=False`/`confidence=None` for that cycle and emits a Layer 0 §10
diagnostic. Every result value remains subject to Layer 1's ordinary `EvidenceValue` validation; a
formula never gets an `Any` escape hatch. These are constant-time in-memory validations, so they do
not change §2.2's hot-path I/O contract.

`compute` receives **every** input declared by the owning `FusionRule`, in exactly the declared order,
including facts with `available=False`; it therefore sees the difference between a definitive `False`
and a sensor that supplied no trustworthy observation. `min_inputs` counts only the available members
of that same fixed sequence. Below the floor, the derived `HouseFact` is `available=False` without
calling `compute`; at or above it, the formula itself decides whether the particular unavailable
members permit a sound result. This is essential for asymmetric evidence such as room occupancy: a
positive PIR may establish presence while another sensor is unavailable, but that unavailable sensor
must remain visible before the formula declares the room vacant. The ordered sequence is supplied
from already resolved facts only; it adds no I/O, lookup, or allocation proportional to history on
the hot path.

`compute` returns `None`, not a degenerate tuple, when it cannot produce a value from the complete
input sequence it was given — for example, enough inputs are available by count but the particular
combination remains contradictory or insufficient for the formula's own safety rule. Either path —
the `min_inputs` gate or `compute` returning `None` — ends the same way: `available=False`, with no
confidence function called.

#### Generic numeric hysteresis condition

The core registers `numeric.hysteresis_condition.v1` with separate
`implementation_version="1"` as a closed, reusable `FormulaStrategy`
configuration. It takes exactly two ordered inputs: one
current-cycle canonical numeric state `FactRef`, then its own boolean output
with `previous_cycle=True`; it produces a boolean state at the numeric input's
`Location`. Its configuration has exactly `source_unit`, `direction` (`above`
or `below`), `entry_threshold`, and `exit_threshold`. The compiler requires
finite, non-boolean thresholds and rejects extra fields. The binding validator
requires the declared canonical unit to equal the numeric source claim's unit,
one exact boolean output claim, the same Location, and the permitted self-memory
position. For `above`, entry must exceed exit; for `below`, entry must be less
than exit. All parameters and the formula implementation version enter the
ordinary fusion fingerprint. There is no resident-supplied expression or
runtime registry lookup.

For `above`, a current value `>= entry_threshold` yields `True`, a value
`<= exit_threshold` yields `False`, and a value strictly between them retains
the available previous boolean output. For `below`, reverse the inequalities:
`<= entry_threshold` yields `True`, `>= exit_threshold` yields `False`, and
the middle retains the previous boolean. An unavailable, stale, invalid or
wrong-unit current value yields `available=False`, never a remembered value.
When previous-cycle memory is unavailable or invalid and the current value is
between thresholds, the output is unavailable until an entry or exit boundary
establishes it. This includes first startup and unclean recovery; a clean
restart may use only the matching pre-hydrated previous-cycle snapshot (§5.8).
The entry uses `min_inputs=1` and `confidence_mode="inherit_input"`.
At an entry or exit boundary it inherits the numeric source's confidence;
inside the band, with valid memory, it chooses the lower confidence of the
current numeric source and previous boolean output, breaking a tie toward
the numeric source. This uses the existing `InheritedFormulaResult` input
index and cannot increase confidence by remembering a less certain state. Its
`FusionRule.stability` is `None` when used as a Reaction trigger: any action
dwell belongs to Layer 5 and must not be counted again here.

For irradiance-triggered `environment.solar_shading`, staging binds one such
boolean output to the `environment.incident_solar_exposure.<solar_binding_id>`
fact from `environment.solar_incidence.v1` in `incident_irradiance` mode for
the subject opening. Layer 5 consumes this exact output as its qualifying
condition; Layer 3 binds its episode and `FutureStateFractionOutcome` to the
same boolean state stream. Entry/exit thresholds therefore have one staged
owner in the Layer-2 formula, rather than two independent copies in the
Reaction and learner. The geometry-only proxy is rejected for this binding.

#### Environmental formula configurations

The core registers `environment.solar_incidence.v1` with one closed
configuration object: `opening_id`, `solar_binding_id`, and `mode` equal to
`geometry_proxy` or `incident_irradiance`. Its pure compiler rejects extra
fields; its binding validator resolves the registered opening and its
orientation from the staged Topology. The frozen core compass-azimuth mapping
accepts exact `north`, `northeast`, `east`, `southeast`, `south`,
`southwest`, `west`, or `northwest`, maps them to 0, π/4, π/2, 3π/4,
π, 5π/4, 3π/2, or 7π/4 radians clockwise from north, and rejects an
unsupported string. Its version and the exact opening/topology fingerprint
enter the compiled configuration. The first mode requires current
`external.solar_elevation` and
`external.solar_azimuth` inputs at `casa` and produces a dimensionless
`environment.solar_incidence_proxy.<solar_binding_id>` at the opening's room.
The second additionally requires typed direct-normal and diffuse irradiance
inputs and produces W/m²
`environment.incident_solar_exposure.<solar_binding_id>`. The stable output
suffix resolves to exactly that opening; an unknown opening, incompatible
room, duplicate binding/output claim, missing orientation or wrong input
unit/shape rejects staging. Both solar-angle facts use canonical radians
with the same north/clockwise azimuth convention (§3.6). A Topology change invalidates the compiled
formula and dependent learning definitions. Evaluation uses only the frozen
orientation and current typed inputs, never a Topology lookup or HA metadata.
The geometry/irradiance interpretation is exactly Layer 3 §4.8.2; no proxy
is mislabeled irradiance. The geometric direct component is exactly zero
when the current solar elevation is at or below the horizon; the descriptor
cannot infer daylight from an opening's azimuth alone.

The core registers `environment.humidity_ratio.v1` with one closed pressure
source choice. `pressure_source="fact"` requires a staged pressure `FactRef`
as the third input, in canonical pascals; it forbids a reference-pressure
value. `pressure_source="reference"` instead requires one developer-declared
finite positive `reference_pressure_pa` and forbids a pressure input. Both
forms require temperature and relative-humidity inputs in their canonical
units, exactly one output
`environment.humidity_ratio.<humidity_binding_id>` in kg water/kg dry air,
and a registered stable `humidity_binding_id` in the closed configuration.
The compiler/validator reject unknown fields, invalid source combinations,
unresolved refs, wrong location/unit, non-positive pressure or duplicate
claims. At runtime a required unavailable input, a pressure not greater
than computed vapor pressure, or a non-finite result returns `None`; no
reference-pressure fallback is taken in `fact` mode. The formula uses the
Layer-3 §4.8.3 psychrometric equation, not relative humidity as a substitute.

Both entries use `confidence_mode="inherit_input"`: after all required
inputs are available, the result inherits the lowest current input
confidence, with fixed input-order tie-breaking. Their `min_inputs` is two;
the compiled mode validator requires the additional inputs where declared,
and `compute` returns `None` if a required input is absent. Their compiled
configurations and exact formula implementation versions enter the ordinary
FusionRule execution fingerprint. The other Initial-V3 formulas keep
`configuration=None` unless their own core registration explicitly declares
another closed compiled type.

#### `physical_evidence.weighted_evidence`

This registered core formula has `confidence_mode="categorical"`, `min_inputs=1`, and requires one
configuration JSON object with exactly `bindings`, `true_threshold`, and `false_threshold`. Each
`bindings` entry has exactly `input_index`, `role`, `true_weight`, `false_weight`, and
`required_for_false`. Its `compile_configuration` validates this JSON and builds the internal typed
`PhysicalEvidenceWeightedConfig`. `validate_binding` then resolves `admission` and
`correlation_group` from the corresponding staged `Sensor` into a `ResolvedPhysicalEvidencePlan`.
Neither step nor `compute` consumes raw JSON. The admin therefore assigns a source's quality profile
once, in its Sensor registration, instead of copying it into every fusion that uses the source.

Its `validate_binding` permits exactly one of two homogeneous shapes: it either produces
`occupancy.physical` at a room from same-room `occupancy.evidence.<kind>.<sensor_id>` inputs, or it
produces `presence.physical` at `casa` from `presence.evidence.<kind>.<sensor_id>` inputs. It permits
no `previous_cycle=True` input. Every referenced Sensor has the required evidence profile from §2.4,
and the one-to-one configuration binding/index contract is verified during staging. `<kind>` remains
opaque: a new normalized evidence kind needs a Sensor binding, not a formula-code change.

Only an available input whose `value` is exact `bool` participates. An available non-boolean input is
a formula-contract violation: this cycle returns `available=False` with a diagnostic, never Python
truthiness. Inputs are first reduced by `correlation_group`, before any role or weight is considered.
A group with both available `True` and `False` observations is conflicted and contributes no vote; a
non-conflicted group contributes at most one directional vote, using the largest weighted confidence
among members reporting that direction. Thus sibling entities, multiple outputs from one vision
pipeline, or readings known to share a failure mode can never manufacture an independent quorum.

For each retained directional group vote, let `c` be the selected fact's non-`None` provenance
confidence. Its group-wide staged profile supplies the corresponding `true_weight`, `false_weight`,
role, admission, and required-for-false setting. A `True` contributes `true_weight * c` to
`true_score`; a `False` contributes `false_weight * c` to `false_score`. The formula returns:

1. `value=True` when at least one available, non-conflicted `primary` input with
   `admission="immediate"` is `True`, or `true_score >= true_threshold`.
2. `value=False` only when step 1 did not apply, every `required_for_false` group is represented by an
   available non-conflicted `False` vote, and `false_score >= false_threshold`.
3. `None` in every other case, producing `available=False`.

`primary` describes the configured fusion role, while `admission` constrains what the Sensor is ever
allowed to do: a `corroborating` source may be a weighted supporting vote but can never take the
immediate-primary shortcut. Staging additionally prevents a single corroborating group from meeting
an instant true threshold; it must have either an independent quorum or the rule's positive true
confirmation dwell. For a `True` result, categorical `support` is `true_score`; for `False`, it is
`false_score`. In both cases categorical `total` is the sum of the configured
directional weights of every retained, non-conflicted group vote **before**
multiplication by that group's selected fact confidence: use `true_weight` for
a `True` vote and `false_weight` for a `False` vote. The selected group's
confidence must be finite and in `[0, 1]`, so `0 <= support <= total` even
when weights exceed 1. A produced `True` always has `total > 0`, including
the immediate-primary case with confidence zero; a produced `False` reaches
a positive `false_threshold` and therefore also has `total > 0`. The formula
calls Layer 1's categorical confidence only after these conditions hold.
For example, a sole immediate primary with `true_weight=2` and confidence
`0.2` produces `True` with `support=0.4`, `total=2`, confidence `0.2`;
confidence zero produces `support=0`, `total=2`, confidence zero. An
independent `False` vote with `false_weight=1`, confidence 1 changes the
first case to `support=0.4`, `total=3`, confidence `0.4/3` when the immediate
primary still selects `True`. Two correlated same-direction inputs yield
only the selected group's one weight in `total`; contradictory observations
in one group yield no vote. An unavailable input contributes neither
fabricated evidence nor a fake `False`. The formula has no dwell or retained state: `FusionRule.stability` remains the sole owner of
delayed exit and of the separate cross-strategy unavailable-grace policy (§5.2).

**Fast/confirmed use of one fusion.** When a physical conclusion has both
high-specificity and potentially noisy evidence, Initial V3 stages one
`physical_evidence.weighted_evidence` fusion over normalized Sensor evidence,
with one physical output. A true `primary` source explicitly admitted as
`immediate` takes the formula's same-cycle shortcut. Corroborating sources
have no shortcut: with `Stability(to_true=None, ...)`, no single
corroborating group may meet `true_threshold`; two or more independent
groups must jointly reach it. A setup has both routes only if at least two
staged, distinct corroborating groups can jointly reach the threshold
without any immediate source. Otherwise it has only the immediate route.
The one fusion owns the ordinary declared false stability. No intermediate
physical fact, FusionRule input to this formula, separate true dwell, or
special deadline is needed. This recipe applies equally to occupancy,
presence, or another registered physical boolean family. Other legal
formula configurations may still use an explicitly positive true dwell;
they are not this two-route recipe.

Core-team-curated, not admin-authored and not open to third parties — same governance as
`PatternLearnerConfig` (Layer 3: "declared in code only... no learning family is admin-authored
today"). A `FormulaStrategy(formula_id=...)` looks up its `RegisteredFormula` here; the registry can
grow through a core specification change without ever touching `FusionStrategy` or the code that pattern-matches on it. Mirrors
`NormalizationFusionRegistry`'s existing plugin pattern in the current codebase — not a new
mechanism, the same one, given an explicit home in this model.

### 5.4 Confidence per strategy — the mapping Layer 1 deferred here, now closed

Layer 1 (§4.2) owns three pure confidence functions and one non-computation option, and states that
*which* applies to a given producer is Layer 2's decision. Resolved for all five strategies:

| Strategy | Confidence treatment |
|---|---|
| `DirectStrategy` | Inherit — the single source's own `confidence`, unchanged. |
| `WeightedQuorumStrategy` | `categorical_confidence(winning_weight, total_weight_considered)` — the same-cycle votes *are* the "observations" (Layer 1 §4.2's `total_observations` is deliberately general for exactly this). Let `weight_for` be the total weight of inputs voting "for" (the side compared against `threshold`). **Resolved 2026-09-07 (corrected a self-referential formula found in review)**: `winning_weight = weight_for` when `weight_for >= threshold` (the threshold was reached — this is the weight actually backing the reported `True`); `winning_weight = total_weight_considered - weight_for` when it wasn't (the weight actually backing the reported `False` — the weight that did *not* vote for, never `weight_for` itself, which would report higher confidence for a near-miss than for a unanimous rejection). `total_weight_considered` excludes any `available=False` input entirely (§5.5). **The `False` branch has three distinguishable sub-cases — see below.** |
| `PrecedenceStrategy` | Inherit — the first definitive (available) source's own `confidence`; if every `inputs` entry is `available=False`, none wins and the derived fact is itself `available=False` (§5.5), following directly from the strategy's own definition. |
| `FormulaStrategy` | Determined mechanically by its `RegisteredFormula.confidence_mode` (§5.3): `continuous` calls `continuous_confidence`, `categorical` calls `categorical_confidence`, and `inherit_input` copies the declared available input's confidence unchanged. |
| `UnanimityStrategy` | `combined_confidence(...)` — see below, the one genuinely new case. |

**`WeightedQuorumStrategy`'s `False` branch collapses three distinguishable situations into the same
formula — worth naming explicitly, because one of them produces a confidence value that looks
alarming out of context (resolved 2026-09-08, second-audit finding).** `winning_weight =
total_weight_considered - weight_for` is correct arithmetic in all three; what differs is what the
result *means*:

- **Partial dissent** — some considered inputs voted "for," some didn't, `threshold` wasn't reached.
  `winning_weight` is the real weight of the dissenters; `confidence` scales with how much of the
  considered population actually disagrees. The ordinary case, already covered above.
- **Unanimous rejection** — no considered input voted "for" (`weight_for = 0`). `winning_weight =
  total_weight_considered`, `confidence = 1.0` — every available voice disagrees, maximal confidence
  in `False`. Also ordinary.
- **Unanimous non-dissent below a fixed threshold** — every considered input voted "for" (`weight_for
  = total_weight_considered`), yet `threshold` (an absolute bar, calibrated for the strategy's full
  configured population, not for whatever happens to be available this cycle) still isn't reached
  because availability has shrunk — e.g. 5 sensors at `weight=1` with `threshold=5.0`, 2 go
  `available=False`, the remaining 3 are unanimously "for," `weight_for = total_weight_considered =
  3`, `3 < 5` so `False` is reported anyway. `winning_weight = 0`, `confidence = 0.0`. **This is
  intentional, not a defect**: zero of the considered weight actually contradicts the opposite
  outcome — the reported `False` is an artifact of comparing a fixed bar against a shrunken
  population, not a judgment backed by any dissenting evidence. A `confidence` of `0.0` here is the
  honest signal: this `False` is exactly as untrustworthy as the evidence backing it, which is none.

A fixed `threshold` was a deliberate choice (§5.1 — an admin-configured absolute bar, unlike
`UnanimityStrategy`'s population-relative "all"), so this third sub-case is not a formula defect to
fix by rescaling `threshold` to the shrunken population — that would just turn `WeightedQuorumStrategy`
into a re-weighted `UnanimityStrategy` and erase the reason the two strategies coexist (§5.1's own
comment on why `UnanimityStrategy` can't be expressed as a fixed `WeightedQuorumStrategy` threshold,
and vice versa here). **Operational recommendation, not a structural requirement**: whoever sets
`threshold` close to the strategy's full configured weight should set `min_available_weight` (§5.5)
close to `threshold` too — that keeps the derived fact `available=False` once availability drops
enough to produce this sub-case, instead of emitting a `False` at `confidence=0.0` that a careless
consumer might mistake for an ordinary low-confidence reading rather than "don't trust this at all."

**`UnanimityStrategy`, worked out from Layer 1's `combined_confidence` (§4.2), by De Morgan symmetry
across the outcome branch** (two branches, not four — resolved 2026-09-08 alongside dropping the
"any" mode, §5.1: the "any" pair of branches this table used to carry is now
`WeightedQuorumStrategy`'s ordinary confidence treatment above, at `weight=1`/`threshold=1.0`):

- Outcome `True` (a conjunction — every considered source agreed): `combined_confidence` over **all**
  considered sources' `confidence`, `combinator="min"` — an AND is only as trustworthy as its weakest
  agreeing premise.
- Outcome `False` (equivalent to "at least one disagreed" — a disjunction over the dissenting
  sources): `combined_confidence` over the **dissenting** sources' `confidence`, `combinator="max"`.

### 5.5 `available=False` inputs and fusion strategies

For `DirectStrategy`, `UnanimityStrategy`, `WeightedQuorumStrategy`, and `PrecedenceStrategy`, an input
(whether `Sensor`- or `FusionRule`-produced, §5.6) with `available=False` (§3.2) is **excluded** from
whichever population feeds the strategy and its confidence computation — never treated as a `False`
vote for `UnanimityStrategy`, never contributing weight to `WeightedQuorumStrategy`'s total. If this
leaves nothing to combine, the derived `HouseFact` is itself `available=False`, and no confidence
function is called at all (Layer 1 §4.2's "no meaningful confidence for nothing observed" rule).

For `UnanimityStrategy`, absence is deliberately not a negative assertion: treating an offline input
as `False` would manufacture dissent (for example, an unavailable door contact would claim that a
door is open). `min_available` is mandatory precisely so a configuration must state how much partial
availability it accepts; `min_available=len(inputs)` makes every configured input required, while a
smaller value retains the same exclusion semantics but opts into degraded operation explicitly.

`FormulaStrategy` is the deliberate exception: §5.3 passes the full ordered input sequence to the
formula so it can make a formula-specific distinction between negative evidence and missing evidence.
Its generic availability gate is `min_inputs`, counted only over available facts; it never receives
fresh data or bypasses the formula-result confidence validation. A formula must not treat an
unavailable input's `value` or `confidence` as meaningful, and an inherited-confidence result may
select only an available input. This exception is narrow and does not change the exclusion semantics
of the four closed generic strategies.

For the two boolean vote strategies, this exclusion applies **only** to inputs already marked
`available=False`. An input marked available but carrying a non-boolean value is not another form of
unavailability; it follows the Boolean vote contract in §5.1 and invalidates that fusion result for
the cycle with a diagnostic.

**Excluding unavailable inputs can leave *something* to combine while still leaving too little to
trust — a distinct problem from the empty-population case, with its own gate, not folded into
`confidence`.** If 4 of a `WeightedQuorumStrategy`'s 5 configured sensors go `available=False`
simultaneously (a Zigbee segment losing power, say), the remaining one sensor's vote is not "empty" —
`categorical_confidence` would happily compute a confident-looking ratio from it alone, even though
almost nothing was actually observed. This is exactly the distinction Layer 1 §4.2 already draws for
`min_support` — "enough data to trust this at all" is a separate boolean gate from "how much the data
agrees" — applied here to input *completeness* rather than sample count: `min_available_weight`
(`WeightedQuorumStrategy`) and `min_available` (`UnanimityStrategy`), both declared alongside their
strategy (§5.1). Below the floor, the derived `HouseFact` is `available=False` — same outcome as the
fully-empty case, same reason, just a less extreme trigger — never a technically-correct but
misleadingly confident number computed from a handful of survivors. This is deliberately a **local**
gate, per `FusionRule`, not a duplicate of Recovery's system-wide `degraded_recovery` classification
(Layer 0 §7.1): Recovery's classification is about the overall runtime, and would not necessarily
fire when only this one `FusionRule`'s specific inputs are affected while the rest of the house's
entities are fine — the two operate at different granularities and are not meant to substitute for
each other.

### 5.6 A `FusionRule` may consume another `FusionRule`'s output

**Resolved 2026-09-04, developer-requested performance review.** `FactRef` (§5) addresses an input by
`fact_type`/`Location`, never by producer id — so nothing in `FusionRule` itself distinguishes "this
input came from a `Sensor`" from "this input came from another `FusionRule`". A `FusionRule` may
freely list, in `inputs`, a `FactRef` that another `FusionRule`'s own `produces`/`where` matches.
Concrete motivating case: "zone occupancy" reusing "room occupancy" (itself already a
`physical_evidence.weighted_evidence` `FusionRule`) instead of re-deriving from every room's raw sensors again,
duplicating weights/threshold/stability across every consumer that wants a coarser view.

**Why this is safe for the "decide and act fast" goal, not a regression from the earlier "two waves
only" position.** `FusionRule` is core-team-authored only (§2.1) — the dependency graph between
`FusionRule`s is therefore **static and fully known before the engine ever runs a cycle**, not
something that changes at runtime. This means the two expensive-sounding operations — detecting a
cycle (a `FusionRule` must never depend on itself, directly or transitively) and computing an
evaluation order — happen **once, at registration/startup**, via a standard topological sort over the
`FusionRule` dependency graph (an edge from A to B when A's `produces`/`where` matches one of B's
`inputs` — well-defined only because §2.3 guarantees exactly one producer per `(fact_type,
Location)`, so this edge is never ambiguous). Only `FactRef`s with `previous_cycle=False` (§5, the
default) contribute an edge to this graph. A validated FormulaStrategy self-memory reference is
excluded because it reads an immutable prior value, not a current-cycle producer; every other
`previous_cycle=True` reference is rejected during staging (§5.8). A registration that
would introduce a cycle among the remaining, current-cycle edges is rejected at startup, loudly,
never silently accepted. Per-cycle, the engine simply evaluates `FusionRule`s in that precomputed order — one wave
per level of real chaining, not a fixed two. The actual latency cost is therefore proportional to how
deep the *real* dependency graph gets, which stays small under core-team curation (nobody is
registering 50 levels of derived aggregates) — the earlier "cap at two waves" position was protecting
against a cost that a registration-time topological sort already avoids paying per cycle.

**The real performance risk from chaining is not compute time — it's `stability` (§5.2) stacking, and
it deserves to be understood precisely, not just flagged.** Each additional level of chaining is
still pure, synchronous computation (§2.2) — microseconds, not a measurable latency concern on its
own. The actual risk is that **debounce windows accumulate across levels, silently, for whoever
configures a higher tier without knowing what a lower tier already waited.** Worked through with
concrete numbers:

- Tier 1 — `physical_room_occupancy` (`FusionRule`, `physical_evidence.weighted_evidence` over
  the room's evidence Sensors,
  producing `occupancy.physical`):
  `Stability(to_true=None, to_false=Window(seconds=120))`. Occupied is reported instantly; vacant is
  reported only after the room has read empty for 120s.
- Tier 2 — `physical_zone_occupancy` (`FusionRule`, `inputs` = several rooms'
  `physical_room_occupancy` `FactRef`s,
  `WeightedQuorumStrategy(weight=1` for each, `threshold=1.0)` — "any room occupied," §5.1's
  redundancy-with-`UnanimityStrategy` note): if configured with its *own*
  `Stability(to_true=None, to_false=Window(seconds=60))`, the intent is "wait 60s before calling the
  zone vacant." But tier 2 is watching tier 1's **already-debounced** output, not the raw sensors — so
  the zone doesn't actually go vacant until `physical_room_occupancy` itself commits vacant (120s after the
  room emptied) *plus* tier 2's own 60s dwell on top of that. **Total: 180s, not 60s** — a number
  nobody configuring either tier in isolation would arrive at by reading either one's own definition.
- The instant-on side does **not** compound the same way: if every tier uses `to_true=None`, an
  "occupied"/"true" transition stays instant no matter how many levels are chained, since a `None`
  window never waits regardless of what fed it. The stacking risk is specific to the debounced
  direction — good news for exactly the kind of case (a light that must react immediately) that
  motivated `Stability` in the first place, but no reason to treat the debounced side as low-stakes:
  an unexpectedly slow "vacant"/"off" propagation is still a real, user-visible correctness problem
  (e.g. security arming logic waiting 3 minutes longer than anyone intended to treat a zone as clear).

**Resolved as staged visibility, not a structural restriction.** Stability remains legal at every
semantic level. During `RegistryGeneration` staging, after the same-cycle Fusion DAG is topologically
resolved, Layer 2 computes a `StabilityPathSummary` for every `FusionRule`: the maximum cumulative
delay and one deterministic input path that realizes it, separately for the two transition directions.

```python
@dataclass(frozen=True)
class StabilityPathSummary:
    to_true_delay: Window | None
    to_true_path: tuple[str, ...]    # upstream fusion_ids, then this fusion_id
    to_false_delay: Window | None
    to_false_path: tuple[str, ...]
```

For a plain symmetric `Window(seconds=s)`, both directions add `s`; for `Stability`, `to_true=None`
or `to_false=None` adds zero in its respective direction. A summary delay of `None` means exactly
zero elapsed time; every positive summary delay is a `Window`. The summary adds the rule's own delay to the
largest matching-direction summary of any current-cycle upstream Fusion input; a Sensor input starts
at zero. A `previous_cycle=True` input is not a same-cycle propagation path and contributes no delay.
Tied paths are selected by stable `fusion_id` order, making the diagnostic reproducible.

The summary is immutable active-generation metadata, exposed to diagnostics and the future panel. It
does not alter candidate evaluation, arm a job, enter a semantic fingerprint, or impose a warning
threshold. Thus a room-level 120-second false dwell followed by a zone-level 60-second false dwell
reports `to_false_delay=Window(seconds=180)` and the responsible chain, while both independent debounces remain valid.
This makes end-to-end latency reviewable without inventing an arbitrary limit or forbidding a useful
semantic separation.

### 5.7 Source location vs. destination location

**Resolved 2026-09-05.** Every `FactRef` in `inputs` carries its own **source location**
(`FactRef.where` — where that specific input was observed); `FusionRule.where` is the derived fact's
own **destination location** (what the derived fact is *about*). Nothing related these to each other
until now. The right relationship turns out to differ by how a strategy actually uses its inputs, not
to be one blanket rule — worked out per strategy:

- **`DirectStrategy`**: exactly one input — a registration-time arity check (previously only implied
  by the word "one" in prose, never actually verified). The destination always equals that one
  input's source location; `DirectStrategy` relabels `fact_type` only, never `where` (§5.1's dataclass
  comment previously said it could relabel "a new fact_type/Location" — corrected: no concrete use
  case exists for changing location while passing a value through unchanged, and allowing it would
  quietly defeat the point of stating an invariant here at all). `FusionRule.where` is still a
  mandatory field regardless of strategy — for `DirectStrategy` specifically, a configured `where`
  that doesn't match the single input's `Location` is rejected at registration time (clarified
  2026-09-08), the same discipline as every other registration-time invariant in this document, not a
  value silently overridden by the derived one.
- **`UnanimityStrategy`/`WeightedQuorumStrategy`/`FormulaStrategy`**: these three combine *all* their
  inputs simultaneously, in the same cycle, into one value — by construction, the result is about the
  combined scope of every source, never something finer than any one of them. The destination must
  equal, or be coarser than, the smallest `Location` containing every input's source location (the
  "join") — a coverage check, not a simple membership check, since a source can itself be `zone`- or
  `rooms`-scoped, not only `room`-scoped: every room covered by every source location must also be
  covered by the destination location. Concretely: a `casa` destination is always valid, regardless of
  input locations, since `casa` covers every room; a `zone` destination is valid only if every room
  covered by every source (a source `room`'s single room; every room in a source `zone`'s `room_ids`,
  Layer 1 §6; every room in a source `rooms` set) is a member of the destination `Zone`'s own
  `room_ids`; a `room`/`rooms` destination is valid only if every room covered by every source is
  already exactly that room or a member of that destination's room set. Checked at registration time,
  in the same pass that already walks every `FusionRule`'s `inputs` for §2.3's producer-uniqueness
  check and §5.6's cycle detection — no new traversal needed.
- **`PrecedenceStrategy`**: deliberately exempt from any such rule. A fallback chain's whole point can
  be "use a coarser or differently-scoped reading as an approximation when nothing more specific
  exists" — e.g. a bedroom's own TRV temperature sensor, falling back to a whole-house outdoor
  reading (`where=Location(scope="casa")`) when the room sensor is unavailable, with the `FusionRule`
  itself declaring `where=Location(room="bedroom")` throughout, regardless of which input actually
  won. A join-based rule here would reject exactly this legitimate, intentional case — this is not an
  oversight, it is the one strategy where source and destination location are allowed to diverge
  freely, by design.

A `previous_cycle=True` self-reference (§5.8) trivially satisfies whichever rule above applies: its
source location *is* the `FusionRule`'s own destination location, by construction (same `fact_type`,
same `where`), so the join is always exactly met, never coarser or narrower.

### 5.8 Temporal self-memory in `FormulaStrategy`

**Resolved 2026-09-12: one explicit form of temporal recursion only.** A
`FactRef.previous_cycle=True` is accepted only as a self-reference inside a `FormulaStrategy`: its
`fact_type` and `where` must exactly equal the owning `FusionRule.produces`/`where`, and the resolved
core formula's `validate_binding` must expressly permit the input's position and count. It resolves
from Layer 0's sealed `PreviousCycleSnapshot` as of the **previous completed** cycle. The snapshot is
pre-hydrated before the DAG only after a clean restart; no `FusionRule` reads disk while evaluating.

This preserves the useful explicit-memory case while rejecting `A(t) <- B(t-1)` and mutual temporal
networks such as `A(t) <- B(t-1)`, `B(t) <- A(t-1)`. Those networks have no same-cycle topological
cycle, but create state machines with opaque initialization and evolution. A demonstrated future need
for delayed reads of another producer requires a separately specified temporal contract; it is not an
implicit capability of every FusionRule.

**Why self-reference is safe here specifically, when §5.6 forbids it in general.** A `FusionRule`
depending on its own *current*-cycle output has no well-defined evaluation order — that is a genuine
cycle, correctly rejected by §5.6's topological sort. A `FusionRule` depending on its own *previous*
cycle's output has no such problem: that value is already fixed, computed, and immutable by the time
the current cycle begins evaluating anything. It is memory, not a dependency requiring an ordering
decision — which is exactly why this validated self-memory input is excluded from §5.6's dependency
graph entirely (it never needs to be topologically ordered relative to anything).

**What this enables: stateful/recursive computation inside `RegisteredFormula.compute`, without
breaking its pure, stateless signature (§2.2).** A `FusionRule(strategy=FormulaStrategy(...))` can list,
among its `inputs`, a `FactRef(fact_type=<its own produces>, where=<its own where>,
previous_cycle=True)`. `compute` receives this exactly like any other input — one fixed-position
`HouseFact` in its complete `Sequence[HouseFact]`, possibly marked unavailable — so `compute` itself
stays a pure function of its given inputs; the
"memory" is made explicit as ordinary data sourced from Persistence (Layer 0 §4), never a hidden side
channel or module-level mutable state. This is what makes a genuinely recursive/temporal computation
expressible with the existing, closed, core-team-reviewed `FormulaStrategy` mechanism — no sixth
strategy needed:

- **A recursive Bayesian filter** (updating a posterior probability cycle over cycle, using last
  cycle's posterior as this cycle's prior) — the motivating case for this section. `compute` reads
  this cycle's raw sensor evidence plus its own previous posterior, returns the updated posterior as
  `value` and a dispersion derived from how far that posterior sits from certainty (0 or 1). It is a
  `confidence_mode="continuous"` formula, feeding `continuous_confidence` (§5.4) through the declared
  contract rather than through a special case.
- **An exponential moving average or a running accumulator** — the same shape: this cycle's raw input
  plus the previous cycle's own accumulated value, combined by whatever formula `compute` implements.

**Startup and failure.** On the very first cycle a `FusionRule` ever runs — no previous cycle exists
yet — a `previous_cycle=True` `FactRef` resolves `available=False` (Layer 0's general "starts clean"
default). It remains in its configured position as `available=False`: if the other available inputs
meet `min_inputs`, the formula is called and can explicitly choose an initialization path; otherwise
the derived fact is `available=False` without calling `compute`. The same conservative availability
applies to the first cycle after an unclean restart, missing/mismatched clean-shutdown marker, or
durable-batch failure not followed by a successful batch: an older durable record is never
misrepresented as the immediately preceding cycle. After a clean restart, Layer 0 pre-hydrates the
declared keys from the matching durable cycle
before evaluation, so recursion continues without a formula-side I/O read. In a running process, even
a durable-batch failure leaves the sealed in-memory snapshot available to the next cycle; after one
new completed cycle, it again supplies the prior value normally.

---

## 6. `Actuator`

`Actuator`'s existing principle — inventory fact only, never a command — is unchanged:

```python
@dataclass(frozen=True)
class ActuatorChannel:
    controlled_channel: str            # stable canonical id, unique within its Actuator
    channel_kind: str                  # one closed core semantic channel kind
    observable_state_contract_id: str  # closed core contract for valid physical control edges
    actuation_adapter_id: str          # closed core adapter binding; never an HA service/feature snapshot
    hold_scope: Literal["channel", "changed_facets"] = "channel"
                                          # optional administrator choice; only staged when the
                                          # versioned adapter proves complete affected-facet sets

@dataclass(frozen=True)
class Actuator:
    actuator_id: str
    entity_id: str
    where: Location
    opening_id: str | None = None       # which physical opening this actuator operates, when
                                          # applicable (a shutter) — a mechanical sub-detail of a
                                          # room-scoped actuator, not a WHERE tier of its own
    display_name: str | None = None
    actuator_role: str | None = None    # coarse role, e.g. "light", "shutter", "hvac_unit",
                                          # "water_valve", "switch" (a generic on/off outlet whose
                                          # controlled load Heima doesn't otherwise know). Resolved
                                          # 2026-09-06: deliberately a plain str, not a closed enum —
                                          # same reasoning, and the same words, as Layer 1 §3's
                                          # fact_type: "a closed vocabulary here would fight" routine
                                          # growth. Home Assistant itself has no closed vocabulary of
                                          # device domains/classes — it adds new ones continuously —
                                          # so closing this here would mean a new HA device class
                                          # cannot be represented until a core-team code release,
                                          # exactly the risk the naming convention exists to avoid.
                                          # Role is a coarse, non-exhaustive hint for Layer-8
                                          # candidate suggestions and sibling-role discovery
                                          # (below) — not a runtime capability or admission model.
                                          # A Reaction binds staged channel contracts, never a
                                          # role-string lookup. HA's own richer
                                          # per-entity data (domain, device_class, supported
                                          # features) remains authoritative only at the application
                                          # boundary; it is never duplicated into this field or used
                                          # as an unstaged Reaction admission vocabulary.
    channels: tuple[ActuatorChannel, ...] = ()
                                          # zero or more registered logical control dimensions. An
                                          # unsupported/observation-only HA endpoint remains a valid
                                          # Actuator with no Heima-actuable channel.
    device_id: str | None = None        # same HA device_registry reference as Sensor.device_id
                                          # (§3), for panel grouping + sibling-role discovery
    hold_duration: Window | None = None   # one positive administrator setting shared by all
                                          # fixed-duration channels of this Actuator; omitted
                                          # when every channel uses next-step release
    power_recovery_policy: Literal["reconcile", "never", "require_confirmation"] = "never"
                                          # resolved 2026-09-09: per-actuator policy for Layer 0 §7.4's
                                          # baseline-plus-current-evaluation recovery. "reconcile"
                                          # permits automatic application of the final current target;
                                          # "require_confirmation" proposes it; "never" records no
                                          # recovery target and never applies one automatically. This
                                          # policy is handed to the ApplyStep-owning layer during
                                          # composition, which records coalesced per-channel Layer-0 snapshots on
                                          # accepted target changes; Layer 0 never queries this live
                                          # registry at recovery time.
```

### 6.1 Registered logical channels

An `Actuator` owns one HA command endpoint; an `ActuatorChannel` identifies one logical, observable
control dimension of that endpoint. `controlled_channel` is stable across cycles and unique within the
owning `actuator_id`; it is the identity used by Layer 0 resident-control evidence, Layer 3 candidate
membership, and Layer 5 correction attribution. It is neither an HA entity attribute name nor a free
policy label. Staging rejects duplicate channel ids, an unknown `channel_kind`, state contract, or
adapter id, and any channel whose core contracts cannot bind to the Actuator's registered endpoint.

`channel_kind`, `observable_state_contract_id`, and `actuation_adapter_id` name closed core-owned
registries. Their vocabulary is deliberately smaller than Home Assistant's device-domain and supported-
feature universe: it represents only control dimensions Heima can observe, reason about, and address
safely. A new or otherwise valid HA endpoint therefore does not require a new core release merely to
be represented as an `Actuator`; it gains a registered channel only when a reviewed core contract
exists for it.

The observable-state contract defines the valid physical state and edge shapes for that channel. At
composition it supplies Layer 0 the frozen ingress binding used to recognize a resident control edge;
Layer 0 never performs a live Layer-2 lookup or infers a channel from an arbitrary HA attribute. The
adapter binding identifies a core translation family available to Layer 5. It does not store an HA
service name, service parameters, or a copy of supported features, and this Layer does not issue a
command.

The same staged binding declares its finite canonical facet set, each facet's
nonempty `[a-z][a-z0-9_]*` key (at most 64 UTF-8 bytes), and an enforceable
maximum canonical JSON byte length for each normalized facet value. Registry
identities that enter these projections likewise have enforceable maximum
RFC-8785 escaped JSON byte lengths, including any Unicode escaping. Layer 5
uses those declared bounds for the lossless scalar audit/follow-up projection;
Layer 0 §6.1 uses them with bounded identities to prove that every possible
complete channel hold-audit fact remains within Layer 1's depth-two and
8 KiB limits. Staging rejects a binding with an unprovable bound, a colliding
facet key, or a combination whose worst case fails that proof. This is a
storage-shape admission rule for Heima's own projections, not an HA feature
catalog or a restriction on the endpoint's unrelated attributes.
The same proof covers Layer 0 §5.1.1.1's one change-only
`ChannelStateValue` per channel: the adapter must produce a complete valid
canonical facet snapshot and exact changed-facet set for every physical
edge, with each facet encoded as bounded canonical JSON text. If the
complete state cannot fit Layer 1's depth-two/8 KiB limit, staging rejects
that channel contract before action or learning uses it. The resulting
fact type is unique per `(actuator_id, controlled_channel)`; no
administrator-supplied fact name or HA attribute becomes its identity.

Layer 5 selects a closed semantic action intent from its Reaction descriptor, then admits an Actuator member only
when that descriptor permits the member's registered `channel_kind` and adapter binding. The subsequent
intent-to-`ApplyStep` translation is Layer-5 behavior; Home Assistant remains the sole authority for
the concrete service schema and whether the current endpoint supports the resulting operation at
application time. Thus channels are a bounded Heima semantic admission contract, not a duplicate HA
capability catalog.

Two concrete changes from today's model, both already decided, restated here for completeness:
`light` is added as a role in active use (today lights bypass the registry entirely, duplicated as
raw `entity_id`s inside every reaction's `entity_steps`); `room_id` collapses into `where: Location`
for the same reason `Sensor` uses it — one shared WHERE representation instead of each registry
inventing its own room-reference shape. **`opening_id` does not** — corrected 2026-09-08, found in
review: this sentence previously claimed both collapsed, contradicting the field's own comment above
("not a WHERE tier of its own") and the dataclass, which still carries `opening_id` as its own
field — `Location` has no "opening" tier to fold it into (§5 of the Layer 1 spec: `casa`/`room`/
`zone`/`rooms`, nothing finer-grained than a room), so `opening_id` correctly stays a mechanical
sub-detail alongside `where`, not inside it. It is optional: a room light, HVAC unit, switch, valve,
or any other actuator that is not mechanically attached to an opening leaves it unset. When set, the
candidate topology's owning room must be exactly the actuator's room location (§2.4); this catches a
miswired shutter without inventing a false opening relation for ordinary room equipment.

One HA command endpoint has one `Actuator` record (§2.4). This is a command-ownership invariant, not
a restriction on observation: the same `entity_id` can still back Sensor registrations, and one
physical `device_id` can expose several separately commanded entities. It makes divergence detection,
channel divergence detection, accepted target ownership, and recovery checkpointing unambiguous.

Commands live only in whichever Reaction (Layer 5) decides to send them — `Actuator` never issues
one itself, and nothing in Layer 2 reads or writes actuator state beyond this inventory record.

**One `ApplyStep`, one owned endpoint and channel target.** The future Layer-5 `ApplyStep` envelope
references exactly one `actuator_id`, one registered `controlled_channel`, and one typed semantic target.
It may compile to a finite ordered sequence of one-service `ApplyCall`s when an endpoint requires
separate HA services to express one logical state, such as HVAC mode, setpoint, fan speed and swing
mode. Each call contains no caller-selectable `entity_id`, `device_id`, area, label, or other HA target
selector. At execution, the runtime resolves the current Actuator record and constructs the sole HA
target from its `entity_id`; it rejects a call that tries to supply or override a target selector. A
Reaction that needs four independent endpoint/channel targets emits four ordered `ApplyStep`s; a bounded
call sequence is never a multi-target command hidden in one payload.

This is endpoint ownership plus bounded semantic-channel admission, not a Heima capability catalog.
The service name, parameter schema, and whether the current HA entity supports that operation remain
Home Assistant's source of truth and are validated by HA when the step is applied. Heima neither
persists a duplicate supported-feature model nor reimplements service validation. The initial Layer-5
execution contract preserves the Reaction's declared step order; any future concurrency must be an
explicit Layer-5 scheduling policy and cannot weaken the one-endpoint-per-step or per-step provenance
rule.

Descriptor-specific target schemas are defined at their Layer-5 owner, not in this device-agnostic
registry. Layer 2 stages only the registered channel kind, observable-state contract, adapter and
bounded facet vocabulary; Layer 5 checks the target contract against that binding (§6.1 and Layer 5
§6/§7). The adapter's translation row remains responsible for the actual HA service call(s), and HA
remains authoritative for current endpoint support.

`hold_scope="channel"` is the default and needs no administrator input. `changed_facets` is an
optional administrator choice on an individual registered channel, exposed only when the versioned
core adapter can identify every facet affected by every admitted HA call, including predictable
side effects. The administrator never enumerates actions or facet dependencies. If the mapping is
unknown or incomplete, staging refuses the selective scope and uses channel scope; it never
assumes that on/off, position, mode, or intensity has a universal hierarchy.

`hold_duration` is required and positive when any channel of this Actuator is staged for a
fixed-duration Reaction. That one Actuator setting applies to every fixed-duration channel; it
does not cause holds on distinct channels to share an activation time or deadline. The Actuator
may omit it only when none of its channels uses fixed-duration release. The core descriptor, not
an observation source or resident, declares fixed-duration versus next-Reaction-step release.
Staging rejects a next-step mode whose versioned descriptor cannot supply a stable timed step identity and target
change for the same Reaction/channel (Layer 5 §6.0). There is no implicit fallback from
next-step release to `hold_duration`. Holds never survive restart (Layer 0 §6.3).

`power_recovery_policy` similarly does not create a live Layer-0-to-Layer-2 dependency. At
composition, the policy is supplied to the layer that owns accepted actuator targets; that owner
uses Layer 0 §7.4's checkpoint service only for `"reconcile"`/`"require_confirmation"` targets.
Layer 0 later exposes an opaque recovery baseline; it neither looks up an `Actuator` nor issues a
command itself.

---

## 7. Relationship to Layer 0 and Layer 1

- **`HouseFact`/`Provenance` shape**: every `Sensor` and `FusionRule` produces plain `HouseFact`s per
  Layer 1's contract — Layer 2 adds no new envelope, no parallel representation.
- **Confidence functions**: called, never reimplemented (§5.4) — Layer 2's only job is picking which
  Layer-1-owned function applies and supplying its inputs, per the split Layer 1 §4.2 establishes.
  `Sensor.reliability` (§3.2) is the same split applied to raw readings: not a new function, Layer 1
  §4.2 already permits a raw `Sensor` to report other than `1.0` "with a concrete evidentiary
  reason" — Layer 2 is simply where that allowance becomes an actual, declared, reviewable value
  instead of unexercised prose.
- **Storage/timing**: every produced `HouseFact` goes through Layer 0's Persistence and Timing
  exactly as any other fact. `FusionRule.stability` (§5.2) is the one Layer-2-specific addition on
  top: `Window`/`Stability` themselves are comparison values (`Stability` composed of two
  `Window`s), reusing Layer 0's own elapsed-time discipline (§3.2) for the actual check — but the
  pending-transition *tracking* that debounce requires (which candidate is pending, since when) is
  new here, not something Layer 0's `Window` type provides on its own. Every `Window`-typed field in
  this document (`FusionRule.stability`, `Stability.to_true`/`to_false`) accepts a `LearnedWindow` in
  its place, per Layer 0 §3.2's general substitution rule — not restated at each field individually.
- **`FactSource`**: a `Sensor`-produced fact carries `kind="sensor"` — a direct single-binding read.
  A `FusionRule`-produced fact carries `kind="analyzer"`, per Layer 0 §5's now-precise definition
  ("derived from combining or analyzing existing data rather than one direct entity read" —
  `FusionRule` qualifies by that property regardless of being same-cycle and deterministic, not by
  being statistical; this was genuinely ambiguous before Layer 0 §5 got per-value definitions,
  resolved 2026-09-03, `v3_backlog.md`). `source_id` is the `sensor_id`/`fusion_id`, unchanged by a
  `FusionRule` chaining onto another `FusionRule`'s output (§5.6) — that's still just a fact read by
  `fact_type`/`Location` like any other input.
  The fusion also sets Layer-0 `FactSource.route_fingerprint` to a SHA-256
  digest of RFC-8785 canonical JSON over its stable evaluated input route.
  `DirectStrategy` and `PrecedenceStrategy` include the one selected `FactRef`
  and that fact's `FactSourceFingerprint`; `UnanimityStrategy` and
  `WeightedQuorumStrategy` include the canonically ordered considered input
  refs and their source fingerprints. A `FormulaStrategy` includes its
  canonically ordered available input refs and source fingerprints; the
  formula registry may further narrow that list only through a versioned
  declared selection rule. The route excludes input values, confidences,
  timestamps, correlation ids and evidence; those first two are separately
  compared by `FactChangeFingerprint` or affect the output calculation.
  An unavailable or newly selected input therefore changes the route only
  when it changes the evaluated set. The finite registered input list bounds
  this calculation, and the Fusion DAG prevents recursive source cycles.
- **Evaluation ordering**: the topological sort that lets a `FusionRule` consume another
  `FusionRule`'s output (§5.6) is Layer 2's own registration-time mechanism, not something Layer 0's
  Timing owns — Layer 0's `AtJob`/`CronEntry` schedule *when* a cycle runs, not the *order* in which
  Layer 2 evaluates its own registrations within one.
- **Divergence Hold Manager**: Layer 5 passes the validated Actuator channel key, observed
  divergent facets, staged scope, release mode and any fixed `hold_duration` after its own
  physical-confirmation checks (Layer 0 §6). Layer 0 never looks up this registry.
- **`FactRef.previous_cycle` (§5.8)**: supplies only the validated FormulaStrategy self-memory case.
  Resolution reads Layer 0's sealed `PreviousCycleSnapshot` (§4), never the live registry, history
  buffer, formula-side durable query, or bespoke Layer-2 cache. Layer 0 pre-hydrates that snapshot
  before the DAG only after a clean restart; first-ever and unclean-restart cycles resolve
  `available=False`.

Layer 2 depends on both Layer 0 and Layer 1. Layer 0 accepts validated channel keys,
release contracts and configuration deltas supplied at composition; it never queries the Layer 2
registry at runtime.

---

## 8. Not yet decided

Open cross-layer contracts are tracked in the CA4 backlog. No open CA4 item is currently owned by
this layer.

---

## 9. Acceptance criteria (for the eventual implementation phase)

- A registered Actuator channel has a unique bounded normalized
  `ChannelStateValue` projection under Layer 0 §5.1.1.1; its full facet
  snapshot and exact changed-facet set fit Layer 1's depth-two/8 KiB value
  bound. Staging rejects a missing observable facet, noncanonical value,
  duplicate channel identity or unprovable size, while unrelated Actuators
  remain registerable (§6.1).
- A staged state/attribute Sensor with `max_source_age` becomes unavailable
  when the HA source timestamp is missing, future-dated or older than its
  positive `Window`; an unchanged but newly reported value uses `last_reported`,
  not `last_updated`, and an expired report opens stream coverage at the known
  expiry instant without backdating the emitted fact. The ordinary `AtJob`
  checks expiry even when no HA edge arrives, and a newer report re-arms
  that one job without creating an extra fact. A numeric Sensor with bounds rejects a converted value
  outside its finite canonical-unit interval. Neither gate reuses its previous
  value or blocks an unrelated Sensor (§3.2–§3.3).
- When solar geometry is required, the two core-generated `sun.sun` attribute
  Sensors alone claim casa `external.solar_elevation` and
  `external.solar_azimuth`. One snapshot yields both in radians through the
  registered degree converter. A duplicate claim, wrong unit/converter,
  impossible angle, missing attribute, stale/unavailable Sun state or changed
  observer location cannot yield an available solar-incidence input; unrelated
  automations continue. A north- and south-facing opening consume the same
  geometry pair through distinct staged formula configurations (§3.6/§5.3).
- A configured HA `schedule.*` helper can feed the casa-scoped
  `quiet_hours.active` state claim through the ordinary `StateReadBinding` and
  `MappingInterpretation`: active becomes exact boolean `True`, inactive exact
  `False`, and unavailable, unknown or unmapped helper state produces
  `available=False`. Registration rejects a non-boolean output contract or a
  competing producer for that same `(fact_type, Location)`; no Layer-2 guard
  evaluator or recurrence is created (Layer 5 §3.2).
- A third-party producer may pass ordinary producer-claim/fact-contract staging when Layer 7 invokes
  it, but an attempt to register an `Interpretation`, `FusionStrategy`, or `RegisteredFormula` outside
  the core-owned frozen registries is rejected before an active generation exists. No dynamic import,
  callable lookup, or plugin lock occurs during a Sensor/Fusion evaluation (§2.1/§5.3).
- All 9 entity-list mechanisms named in §1 are removed from the codebase, replaced by `Sensor`
  registrations with no residual parallel list left standing.
- Starting V3 in the presence of populated V2 options, history, checkpoints, or learned state reads
  none of them and creates no registry record from them: V3 begins with only the explicitly supplied
  new configuration and cold fact/learning stores. A retained V2 export is never an input to V3
  runtime behavior (§1.1).
- Two room sensors with the same normalized occupancy evidence kind but different stable `sensor_id`s
  register distinct `occupancy.evidence.<kind>.<sensor_id>` facts at one `Location`, are both
  addressable by one room-occupancy `FusionRule`, and remain so after one binding's HA `entity_id`
  changes. Reusing the same namespace suffix or using an HA `entity_id` as the suffix is rejected
  (§3/§2.3).
- Every `Sensor` sets `available=False`/`confidence=None` exactly per §3.2's rule, in a test that
  forces each binding-failure case (`StateReadBinding` reading `unavailable`/`unknown`, nonexistent
  `entity_id`, `AttributeReadBinding` targeting a missing attribute, and
  `CalendarWindowReadBinding` with failed Layer-0 extraction); a `MappingInterpretation(default=NO_DEFAULT)`
  `Sensor` reading a raw state absent from `mapping`; and a `CalendarInterpretation` `Sensor` whose
  current event matches no configured category — plus, to verify the two `MappingInterpretation`
  configurations are actually distinguished and not accidentally conflated, a
  `MappingInterpretation(default=<value>)` `Sensor` reading that same absent-from-`mapping` raw state
  and instead producing `default`, `available=True`, including a separate case where
  `default=None` produces `value=None` with `available=True`.
- Registration rejects every incompatible binding/interpretation pair: calendar bindings are paired
  only with `CalendarInterpretation`, and state/attribute bindings only with mapping, numeric, or
  bucket interpretation. Numeric and bucket tests accept finite non-boolean numeric values and strict
  ASCII decimal state strings (including `12.5`, `.5`, `1e-3`, and signed forms), normalize valid
  values to `float`, and reject booleans, whitespace or
  locale-formatted strings, malformed values, `NaN`, and infinities as an unavailable Sensor with a
  diagnostic rather than a coercion, exception, or selected bucket (§4).
- A `CalendarWindowReadBinding` passes only `active_now` windows to `CalendarInterpretation`: a future
  event matching a higher-priority category cannot change the current Sensor value. Tests verify NFKC/
  casefold/whitespace-normalized `KeywordClassifier` matching, deterministic selection across multiple
  matching active events by its `priority_order`, no-match as `available=False`, and registration
  rejection for an incomplete, duplicate, or extraneous `priority_order`, an empty category list, or
  any empty normalized keyword, including whitespace-only and mixed empty/non-empty lists (§3.1/§4).
  A rejected mixed list cannot classify an unrelated summary through an empty substring. The
  classifier is also tested as a pure text-sequence function independently of
  calendar reads, proving the calendar wrapper does not duplicate matching logic.
- A single HA entity can back multiple `Sensor`s through distinct `ReadBinding`s without violating
  the registry model — verified with one `climate.*` fixture producing separate facts from its primary
  state and at least one attribute, with uniqueness enforced on `(fact_type, Location)` rather than
  on `entity_id`.
- Registration rejects every static numeric/cardinality violation in §2.4: out-of-range or non-finite
  `reliability`; empty, unordered, or prematurely open bucket definitions; an empty fusion input
  tuple; invalid `min_available`/`min_inputs`; non-positive or non-finite weights; a threshold or
  minimum available weight outside its configured-total bounds; and an invalid formula mode's
  `scale`/`floor`; and every invalid `physical_evidence.weighted_evidence` binding/index/threshold
  pair. A
  mapping output/default (other than `NO_DEFAULT`), bucket label, or keyword-classifier category that
  cannot pass Layer 1's `validate_house_fact_value` is likewise rejected in staging rather than
  failing on a later sensor cycle. A valid unit-weight quorum configuration and a valid occupancy
  configuration are accepted, proving
  validation does not reject ordinary registrations.
- Staging rejects duplicate `Sensor.sensor_id` or `FusionRule.fusion_id` even with distinct output
  claims. It rejects `FusionRule.inputs=(A, A)` before any strategy can count one observation twice:
  a unit-weight quorum cannot reach threshold 2 or an availability floor from that duplicate.
  Two separate fusions may still depend on A; a permitted FormulaStrategy may distinguish current A
  from its declared `previous_cycle` self-memory, but may not repeat either exact reference.
- `UnanimityStrategy` configuration must provide `min_available`: staging rejects an omitted value as
  well as values outside `[1, len(inputs)]`. With one unavailable input, a strict
  `min_available=len(inputs)` result is unavailable, while a deliberately lower floor evaluates only
  the remaining boolean votes; an unavailable vote is never fabricated as `False` (§5.1/§5.5).
- Every `FusionRule` strategy's confidence is computed exactly per the §5.4 table — called through
  Layer 1's pure functions, never reimplemented — verified for all five strategies including both
  outcome branches of `UnanimityStrategy` and both branches of `WeightedQuorumStrategy` (threshold
  reached and not reached), the latter specifically with a near-miss case (`weight_for` just below
  `threshold`) verified to produce *lower* confidence than a unanimous-rejection case (`weight_for`
  near zero) — the exact distinction the 2026-09-07 formula correction exists to get right.
- `UnanimityStrategy` and `WeightedQuorumStrategy` accept only exact `bool` vote values: tests verify
  `True`/`False` produce their specified outcomes, while `0`, `1`, `"on"`, `None`, and a structured
  `EvidenceValue` on an otherwise available input produce `available=False`/`confidence=None` and a
  diagnostic, never a coerced or silently excluded vote (§5.1).
- A `FusionRule` with every input `available=False` produces an `available=False` output without
  calling any confidence function, for at least one instance of each strategy.
- A `WeightedQuorumStrategy`/`UnanimityStrategy` `FusionRule` below its configured
  `min_available_weight`/`min_available` — some inputs available, but not enough — produces
  `available=False`/`confidence=None` without calling `categorical_confidence`/`combined_confidence`,
  distinct from and in addition to the fully-empty case above.
- `RegisteredFormula.compute` returning `None`, and a `FusionRule` below a `FormulaStrategy`'s
  `min_inputs`, both produce `available=False` without calling any confidence function.
- A formula receives its complete configured input sequence in stable `FusionRule.inputs` order,
  including an `available=False` fact at its original position; `min_inputs` still counts only
  available members. A formula may return a result using the other available inputs, but an
  `InheritedFormulaResult` selecting the unavailable position is rejected for that cycle with a
  diagnostic (§5.3/§5.5).
- `physical_evidence.weighted_evidence` accepts both validated shapes (`occupancy.physical` in one
  room and `presence.physical` at casa), returns immediate `True` from an available non-conflicted
  `primary` source only when its Sensor admission is `immediate`, and returns `False` only after every
  required-for-false group contributes an available `False` vote and the false score reaches the
  configured threshold. A corroborating source cannot take the primary shortcut. Two inputs from the
  same correlation group never add two votes; a group with contrary observations contributes neither.
  With no true dwell, a corroborating group alone cannot reach the true threshold; with a positive
  true dwell, that same explicit confirmation path is legal.
  A new evidence sensor is added through a binding with no formula-code change. A low-confidence sole
  immediate primary source produces `True` with correspondingly low categorical confidence (§5.3).
  Numerical fixtures prove `true_weight=2, confidence=0.2` yields `0.2`,
  zero confidence yields zero without a zero denominator, an independent
  opposing `false_weight=1` yields `0.4/3` when immediate admission still
  selects `True`, and two correlated votes or a conflicted group are counted
  at most once or not at all. A weight greater than one never yields
  confidence above one.
  A fast/confirmed Initial-V3 fixture stages exactly one physical-output
  fusion with one immediate primary and two independent corroborating groups
  whose combined maximum reaches `true_threshold`, while each group alone
  cannot. It produces a same-cycle `True` from the immediate primary or the
  independent quorum, and prevents same-group duplicates from forging a
  true quorum; no
  intermediate `FusionRule` input or extra physical output is staged.
- Each `FormulaConfidenceMode` is verified independently: a continuous result calls only
  `continuous_confidence` and rejects missing `scale`/`floor` or a non-finite numeric value/dispersion;
  a categorical result calls only `categorical_confidence` and rejects invalid `support`/`total`; and
  an inherited result copies only the indexed available input's confidence and rejects an out-of-range
  index. A result variant that disagrees with its registered mode produces
  `available=False`/`confidence=None` plus a diagnostic, never a guessed confidence (§5.3).
- A `Stability(to_true=None, to_false=Window(seconds=N))` `FusionRule` commits a transition to
  `True` the same cycle the candidate first appears, and a transition to `False` only after the
  candidate has held for `N` seconds — with a test that flips back to `True` mid-window and verifies
  the pending transition is discarded, never partially applied. A positive-dwell transition commits
  from its own one `AtJob` deadline even when no unrelated HA event or periodic fallback occurs; the
  deadline callback re-evaluates current in-memory inputs and cannot commit its arm-time candidate
  after a newer input, token, or generation invalidated it (§5.2).
- A same-value available fusion output with confidence `0.9` then `0.2`
  publishes the second fingerprint without a new dwell. A precedence
  handoff between two available inputs with identical value/confidence
  publishes a changed stable route fingerprint, while repeated evaluation
  of the same route does not. `available=False` then `True` never reads the
  unavailable fact's value; it follows the candidate's ordinary `to_true`
  dwell. A changed source route while a different value is pending does not
  extend its timer; the deadline commits the fresh full fingerprint only if
  the pending value remains valid.
- Staging computes `StabilityPathSummary` without adding runtime work: a 120-second room false dwell
  feeding a 60-second zone false dwell reports a deterministic
  `to_false_delay=Window(seconds=180)` path, while the
  all-`None` true path reports `None` for zero elapsed time. Every positive summary delay
  is a `Window`, never a scalar-seconds field. A `previous_cycle=True` input does not add to either same-cycle
  cumulative delay, and equal candidate paths use stable `fusion_id` tie-breaking (§5.6).
- A candidate becoming unavailable cancels a pending true/false transition, so it can never commit
  from interrupted evidence. With `unavailable_grace=Window(seconds=30)`, the last committed available
  output is retained without per-cycle writes; a fresh candidate cancels the one armed deadline, while
  an unchanged unavailable candidate emits exactly one unavailable fact at expiry. A restart or
  impacted registry reload cancels the grace rather than extending it, and no-grace/security rule
  emits unavailable immediately (§5.2).
- A superseded dwell/grace `AtJob` callback carrying an old `FusionRuleRuntimeState` token cannot
  commit a fact after a newer candidate has re-armed or cancelled it. Runtime state is absent after a
  simulated restart and only direct/transitive impacted fusion ids lose it at a registry reload; no
  test needs a Layer-0 history-buffer lookup to evaluate or clear it (§2.5/§5.2).
- Every `RegisteredFormula` registration is reviewed against §2.2's no-blocking-I/O contract before
  being merged — a checklist item, not an automated test (this cannot generally be verified at
  runtime). The same checklist item applies, and is checked, for every new `Interpretation` decoder
  (§4) and every `FusionStrategy` combination implementation (§5.1) — §2.2 names all three as hot-path
  execution points, not `RegisteredFormula.compute` alone; corrected 2026-09-08, this criterion
  previously only covered the third.
- Formula bootstrap rejects a duplicate id, empty implementation version, or registration after the
  registry is frozen. Candidate staging rejects an unknown formula, non-canonical/oversize/deep
  configuration JSON, a compiler rejection, or a binding rejected by its pure validator before any
  cycle runs; a malformed `physical_evidence.weighted_evidence` payload (wrong field shape/value,
  output, location, input namespace/order, source evidence profile/correlation compatibility, or
  `previous_cycle=True`) therefore never reaches `compute`.
  A test adds a second formula with a different compiled configuration type without changing any
  FormulaStrategy configuration union, and verifies its compiler runs once during staging rather than
  during evaluation.
  A simulated formula-version upgrade impacts and resets only its dependent/transitive FusionRules,
  force-writes their retained facts under the new configuration fingerprint, and leaves an unrelated
  FusionRule's stability and previous-cycle memory intact (§2.5/§5.3).
- `FormulaStrategy` additions (a new `RegisteredFormula` entry) require no change to `FusionStrategy`
  or to any code that pattern-matches on it, verified by adding a second formula in a test without
  touching the union type.
- `environment.solar_incidence.v1` stages separately for a north-facing and south-facing
  opening, freezing each resolved orientation and topology fingerprint. An unsupported
  orientation, duplicate binding, wrong room, missing angle fact, or irradiance-mode
  input without the declared canonical W/m² unit fails staging. Geometry mode yields a
  dimensionless proxy and cannot claim W/m² exposure. At or below zero solar
  elevation, the geometric direct component is zero even for a matching
  opening azimuth (§3.6/§5.3; Layer 3 §4.8.2).
- `numeric.hysteresis_condition.v1` rejects wrong source kind/unit, wrong
  output kind/Location, missing or misplaced previous-cycle self-reference,
  equal/reversed thresholds for its direction, non-finite thresholds and extra
  configuration. For `above` with entry 400 and exit 300, 400 establishes
  `True`, 350 retains a valid previous boolean, and 300 establishes `False`;
  `below` reverses the inequalities. An unavailable numeric input publishes
  unavailable even with remembered `True`; an unknown previous value at 350
  stays unavailable on first startup or unclean recovery. A clean matching
  snapshot may preserve 350's previous state. Boundary results inherit the
  current numeric confidence; middle-band results inherit the lower of that
  confidence and valid previous-output confidence. No Layer-2 dwell is added
  when this fact triggers a delayed Reaction (§5.3, §5.8).
- `environment.humidity_ratio.v1` stages with either a bound pressure fact or a finite
  positive reference pressure, never both or neither. A missing required live pressure
  makes fact mode unavailable without falling back to the reference form; incorrect
  units, duplicate binding, non-finite output and impossible vapor/total pressure fail
  admission or evaluation as specified in §5.3.
- Every light entity a reaction commands is registered as an `Actuator` with `actuator_role="light"`,
  with no reaction's `entity_steps` duplicating a raw light `entity_id` outside the registry —
  `actuator_role` itself is never validated against a closed set (§6), so this checks usage, not
  membership in an enum that doesn't exist.
- Registering a set of `FusionRule`s whose `inputs` form a cycle (directly or transitively through
  another `FusionRule`'s `produces`) is rejected at registration time, loudly, never accepted and
  never discovered only at evaluation time.
- The registration-time topological sort produces a per-cycle evaluation order in which every
  `FusionRule` runs strictly after every other `FusionRule` whose output it consumes, verified for a
  chain at least 3 levels deep.
- A `FusionRule` chained onto another `FusionRule`'s output correctly excludes it from its confidence
  computation when that input reports `available=False` (§5.5), with no special-casing versus a
  `Sensor`-produced input.
- Registering a `Sensor` or `FusionRule` whose `(fact_type, where)` collides with an already-registered
  state producer's is rejected at composition time, loudly, never accepted (§2.3) — verified for a
  `Sensor`-vs-`Sensor`, `Sensor`-vs-`FusionRule`, and `FusionRule`-vs-`FusionRule` collision.
- A candidate registry generation that changes a Zone and thereby invalidates a Fusion coverage check
  is rejected without changing the active generation. A valid semantic change to a Zone, Sensor
  binding/interpretation/unit contract/source-age gate/numeric bounds/reliability,
  FusionRule inputs/strategy/stability, or formula version swaps
  only between cycles, resets `Stability` and prior-cycle output memory only for its full
  direct/transitive current-cycle impact set, force-emits retained
  impacted facts with their new semantic configuration fingerprint, and emits `available=False` for a
  removed producer claim; an unrelated FusionRule retains its pending stability and prior-cycle input.
  A display-name-only change preserves that unrelated runtime state and produces no forced fact write
  (§2.5).
- A Layer-2 registration attempting to use a fact type claimed by another layer — specifically
  `manual_hold.lifecycle` — is rejected before evaluation; a
  `FactRef` to an event fact is rejected for both current-cycle and `previous_cycle` use (§2.3/§5).
- A `WeightedQuorumStrategy` whose `weights` contains a `FactRef` absent from its own `FusionRule`'s
  `inputs` is rejected at registration time (§5.1); an input present in `inputs` but absent from
  `weights` is confirmed to default to weight 1.0.
- Staging rejects a numeric/bucket `Sensor` without a
  `QuantitativeUnitContract`, with an unregistered conversion for differing
  source/canonical units, or with a canonical unit incompatible with a
  staged typed consumer. A state binding staged for `°C` that later reads
  `°F` or no unit reports `available=False`/`confidence=None` and a drift
  diagnostic; it never publishes raw `68` as canonical Celsius. A binding
  explicitly staged with a registered `°F`→`°C` converter publishes
  canonical `20` from `68 °F`. The same rule covers `0.5` fraction versus
  `50` percent and converts before bucket thresholds. An attribute without
  applicable HA unit metadata needs its own developer-declared source unit
  and attribute binding; unrelated entity metadata cannot supply it.
  A nonquantitative metadata mismatch remains diagnostic-only (§3.3).
- A `DirectStrategy` `FusionRule` registered with anything other than exactly one `FactRef` in
  `inputs` is rejected at registration time (§5.7); one registered validly produces output at the
  same `Location` as its single input, verified by a test. A `DirectStrategy` `FusionRule` with
  correct arity (exactly one input) but a configured `where` that doesn't match that input's
  `Location` is also rejected at registration time — a distinct failure mode from wrong arity, tested
  separately.
- A `UnanimityStrategy`/`WeightedQuorumStrategy`/`FormulaStrategy` `FusionRule` whose `where` is not
  equal to or coarser than the join of its `inputs`' source locations is rejected at registration time
  (§5.7) — verified for a `zone` destination missing one input's room from that `Zone`'s `room_ids`,
  and confirmed to succeed for a valid `casa` destination regardless of input locations.
- A `PrecedenceStrategy` `FusionRule` with `inputs` at heterogeneous, unrelated locations — including
  one coarser than its own declared `where` — registers successfully, confirming §5.7's exemption for
  this strategy is not accidentally enforced by the same check as the three aggregating strategies.
- A `Sensor` registered with `reliability=0.85` reports `confidence=0.85` while `available=True`, and
  `confidence=None` while `available=False` regardless of `reliability` — verified across an
  availability transition on the same `Sensor`, to confirm `reliability` never leaks into a fact that
  has no observation to attach it to (§3.2).
- A `Sensor.related_opening_id` is accepted only for a room-scoped Sensor whose room is the owning room
  of an existing Topology opening; unknown openings, a different owner room, or a `casa`/`zone`/`rooms`
  Sensor are rejected during staging. A derived opening-specific fact with sources related to different
  openings is likewise rejected for environmental binding (§3/Layer 3 §4.8.2).
- A live mismatch of a Sensor's applicable registered `unit`, `expected_device_class`, or
  `expected_state_class` emits the corresponding source-shape diagnostic without changing that
  cycle's fact. A malformed raw value still follows the independently tested interpretation-failure
  path, confirming that a metadata diagnostic never silently changes fact semantics (§3.2/§3.3).
- HA-assisted discovery produces no Sensor until the admin accepts a candidate. A temperature-shaped
  state reading may prefill a candidate's binding, unit, and source-shape expectation, but cannot
  register an indoor/outdoor location without the explicit admin decision. A `weather.*` entity
  produces independent attribute-binding candidates, and an AQI or helper candidate is rejected for
  an `outdoor_air_quality` guard until an explicit scale/normalizer or accepted helper output defines
  the required meaning (§3.4).
- An actuable channel with fixed-duration holds requires a positive configured `hold_duration`;
  two fixed-duration channels on one Actuator read that same Window but arm
  independent deadlines from their own hold activation instants (Layer 0 §13).
  Next-step release requires a descriptor with stable future step identity and
  a versioned Layer-5 normal-exit contract for canceled or exhausted programs;
  staging rejects either missing contract. A light or HVAC Actuator staged only for the Initial-V3
  presence-simulation or comfort-trajectory descriptor, respectively, may omit `hold_duration` because
  both declare next-step release; staging requires the positive Window if any fixed-duration Reaction
  also uses that Actuator. An unsupported selective
  scope rejects staging. Restart clears all live holds and the first returned observation cannot
  create one (Layer 0 §6).
- An `Actuator` whose `power_recovery_policy` is `"reconcile"` contributes a coalesced
  per-channel, per-facet desired-target checkpoint only after an accepted target change;
  `"never"` contributes none and
  `"require_confirmation"` reaches Layer 0 recovery as a proposal, not an automatic `ApplyStep`
  (Layer 0 §7.4).
- Registration rejects duplicate `actuator_id`, two Actuators claiming one `entity_id`, and an unknown
  or room-mismatched `opening_id`; accepts a room light with no `opening_id` and two endpoints sharing
  one `device_id`. Reload removing an Actuator or rebinding its stable id to another `entity_id`
  deletes the old recovery target rather than migrating it (§2.4/§2.5/§6).
- An `ApplyStep` targeting an Actuator resolves exactly that record's `entity_id` at the execution
  boundary and rejects a caller-supplied entity/device/area/label target selector. A four-command
  Reaction yields four ordered, individually provenanced steps, including when two commands address
  the same Actuator; HA, not Heima, accepts or rejects each actual service/parameter combination (§6).
- A `WeightedQuorumStrategy` with every `weight=1` and `threshold=1.0` produces exactly the same
  outcome as the removed `BooleanSetStrategy(mode="any")` across every tested availability scenario
  (§5.1), confirming the redundancy that justified dropping it.
- A `FactRef` with `previous_cycle=True` is accepted only for a FormulaStrategy's exact self-reference
  and only when its core `validate_binding` permits it; staging rejects every non-formula, non-self,
  or formula-disallowed prior-cycle input. The accepted self-memory reference contributes no edge to
  §5.6's cycle-detection graph (§5.8).
- On a `FusionRule`'s first evaluation, or the first evaluation after a simulated unclean restart,
  a `previous_cycle=True` input resolves `available=False`; on the next in-process cycle it resolves
  from the sealed in-memory `PreviousCycleSnapshot`. A simulated clean shutdown/restart pre-hydrates
  the declared key before the first DAG and returns the last successfully committed value without a
  formula-side disk read; a durable-batch failure while the process survives does not interrupt the
  in-memory result (§5.8).

---

## Related documents (background only, not required reading)

This spec incorporates and formalizes decisions originally captured in this planning branch's own
`v3_sensors_actuators_draft.md` (Layer A/B, Actuator), `v3_architecture_recap.md` (Layer 2), and
`v3_backlog.md` (the Sensor/FusionRule/Actuator grounding pass, AR-4's `FormulaStrategy` resolution,
and the `combined_confidence` correction). Where this document and any of those differ, this document
is the current word for Layer 2's v3 design.
