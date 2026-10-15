> Superseded for boundary details by [critical review](SOURCE_LOCATION_CRITICAL_REVIEW.md).
> See SOURCE_LOCATION_CRITICAL_REVIEW_MUTANTS.md and the final WORKING_CONTEXT checkpoint
> for current evidence; the original slice results below remain historical.

# Location foundation — impact and implementation choices

Planning HEAD37986ea, read-only; Layer8 CA4-103 changes in progress have no effect
on this owning contract. Layer1 §5 and §10 (L1-LOCATION, no dependencies) define
Location. L0 §4.0 consumes its identity for state keys; L0 §4.5 and L1 §10 require
canonical LocationKey JSON text for a recovered follow-up subject. Existing shared
RFC8785 codec owns JSON encoding. No registry lookup belongs in construction.

Before implementing actual fact SQL, complete this missing mandatory HouseFact
field. Persisting generic placeholders would not implement the universal fact
contract. This slice implements only Location: four validated frozen/slots forms,
canonical key, equality/hash from that key, key JSON text and recovery from that
canonical representation. No fact schema, source authority or batch marker is
claimed. The default Location dataclass object is not a new persisted envelope;
key JSON is the already specified array form.

Require the declared frozenset shape for rooms; do not silently convert malformed
lists/sets, collapse a one-room set into room, normalize opaque IDs, or query a
registry. Recover a canonical key exactly: reject unsorted/repeated room IDs or
wrong arity rather than silently rewriting damaged metadata. The key-text decoder
explicitly accepts canonical key JSON text, as named; generic JSON ingestion and
full HouseFact decoding remain separate. Whitespace, alternate escapes or unsorted
arrays are not canonical persisted key text. Strings are unbounded by a new limit;
no existing 8KiB payload rule is assigned to Location itself.

Planned evidence: exhaustive scope × populated-field decision table; cardinality
0/1/2/3, empty/nonempty IDs, exact Unicode distinctions and BMP/non-BMP ordering;
MC/DC isolates room/zone/rooms payload presence and key arity/order tests. PBT
permutations/round trips and identity mutations. Fresh scoped mutation plus
frozen/slots and wrong-Unicode-order supplements. No new policy or dependency.


## Final evidence and limits

114 new focused instances; full V3 **1074 passed**, seed3145. Exhaustive32-row
scope/optional-field table covers every valid and mismatched shape. BVA covers
rooms cardinality0/1/2/3, empty/minimal IDs, correct/short/long key arity, duplicate
and unsorted recovery, booleans and wrong collection shapes. Opaque Unicode, case,
spaces, composed/decomposed accents and NUL survive unchanged; unknown registry IDs
are allowed until the consuming registry validates them. Explicit BMP/non-BMP
fixture proves code-point room-array ordering independently of shared UTF-16 JSON
object-key ordering. Key-text recovery enforces the named canonical persisted format;
this is not a generic JSON importer or a complete object/fact decoder.

MC/DC: populated room/zone/rooms independently changes shape acceptance at fixed
scope; key scope/arity and canonical sorted/unique rooms are isolated. Equality
changes with ID/scope, hash equals the prescribed key hash, non-Locations return
NotImplemented. Two seeded PBTs exercise permutations/recovery and exact opaque
identity changes. Frozen/slots plus reconstructed-invalid boundary tests enforce
immutable validated use. The follow-up subject fixture round-trips the scalar key
text through the existing shallow projection rules without adding nested rooms.

Ruff lint/format66files,mypy27sources,diff check pass. Fresh mutation177generated,
119killed,58reviewed equivalents (56 error prose,1 redundant guarded branch widening,
1 codec-name case), zero error/timeout/skipped/untested/interrupted. Five semantic
supplements killed with clean114-test baseline. Exact proofs in LOCATION_MUTANTS.md.
No new dependency, normalization, registry behavior, number policy or payload size
limit. Hash is internal/process-local; persist canonical key text, not Python hash.
No full HouseFact, source authority, producer admission, state acceptance, SQL
fact/marker batch, live HA, ARM throughput or deployment verification is claimed.
