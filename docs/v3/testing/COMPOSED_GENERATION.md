# Composed generation record foundation — impact before implementation

Parent66f885b. Planningaa4455a clean/read-only. L0 §4.7/§5.1, registry
L0-COMPOSED-GENERATION, with L1-EVIDENCE-INSTANT and L0-CYCLE-INSTANT
dependencies; read L1 §4 and L0 §3.5.
Admission depends on an active durable composition; that manifest has no value
contract yet. Implement its exact records before a runtime generation fence.

Two pure frozen/slots records: LayerGenerationRef and ComposedGenerationManifest,
exact spec fields. Five layer references exactly once, canonical layer2..layer6
order; reject malformed order rather than silently sort. Explicit UTC effective_at.
All textual fields primitive Unicode without normalization, opaque ids/fingerprint
strings. Validate record shape/encoding, not truth, digest derivation, authority,
parent-chain existence, durable commit or actual activation. No extra fingerprint
hex/length or id grammar invented. invalidated_dependents holds owning-layer
canonical ids as supplied: §4.7 specifies canonical layer order, not a different
ordering/uniqueness grammar for these opaque dependent ids.

No generation controller, manifest writer, port/source authority or durable receipt
added. Records may be staged before commit; construction never proves active status.
No callbacks, implicit clocks, mutable input graph or HA I/O. Dependency work leaves
running producer admission as the next bounded integration step.

Decision/BVA: each layer missing/duplicated/misordered, tuple versus mutable input,
closed layer vocabulary, malformed fields and canonical UTC edge instants. MC/DC:
record-specific applicability documented after implementation. PBT arbitrary opaque
ids/fingerprints survive encoding, permutations rejected except canonical order,
immutable graph and canonical JSON stable. Scoped mutmut and record/vocabulary seeds.
## Evidence and limits

75 focused cases; full V3 **1642 passed**, Hypothesis seed3145. Ruff check/format
85files,mypy33sources and diff pass. Permanent mutation scope now27modules.

Decision tables: every required layer omitted/duplicated, each adjacent swap,
wrong count, closed vocabulary, immutable tuple shape, concrete reference shape,
optional previous id, independent metadata fields and timestamp invalid forms.
BVA: empty/missing/extra/duplicate layer tuple, previous None versus present,
empty/populated dependent tuple, year1/year9999 UTC limits, wrong offsets and
precision, impossible calendar date, primitive/Unicode metadata boundaries.
Opaque metadata is preserved without trimming/normalization or a new digest format.

MC/DC: no compound Boolean decision introduced. Single guards/order equality
and optional-parent branch have explicit decision cases. Reuse shared instant/
canonical validators without duplicating their domain rules.
PBT: all layer permutations are rejected except canonical order; generated opaque
metadata round-trips through canonical JSON, with immutable input tuple detached
from a producer's list. Seed3145 and shrinking enabled. A list returned by Hypothesis
permutations is converted explicitly to tuple by the test before testing order.

Fresh scoped mutmut47generated,23killed,24individually reviewed generic-error-prose
equivalents; no errors/timeouts/skips/untested/interrupted.12 semantic supplements
killed with clean75-test baseline (both frozen/slots decorators,4 order swaps,
unknown-layer addition,3 skipped validation calls). Rejected collection-error
and failed-baseline attempts are not counted. Exact diffs and campaign chronology
in COMPOSED_GENERATION_MUTANTS.md. Source was unchanged after campaign; additional
nested-reference cases strengthen the deterministic semantic supplements.

The records are configuration history, not HouseFacts or depth/size-limited
PersistedProjections. Generic canonical_json_bytes supports their exact tuple/
record fields without a new serializer or cached bytes. Actor attribution belongs
here as specified; it is not added to operational fact source records.

No manifest transaction, impact/definition digest derivation, parent-chain proof,
confirmation check, active-pointer swap, runtime generation fence or producer port
is implemented. effective_at is validated canonical text supplied by the future
commit coordinator; shape validation does not prove it came from that coordinator.
No authoritative generation can be inferred from constructing/decoding these records.
No HA/live/ARM performance/deploy gate claimed; no planning changes or new policy.
