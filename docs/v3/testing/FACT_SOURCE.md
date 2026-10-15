# Source value contracts and stable fingerprint

## Impact and choices before implementation

Planning f191d2c clean/read-only. CA4-103 is now committed (Layer8 map); L0/L1
source and Location contracts unchanged. Read L0 §5/§5.1/§5.2 (L0-FACT-SOURCE,
no dependencies), §4.0 FactSourceFingerprint, and L1 §4. Production trust derives
from runtime boundaries, not a persisted trusted flag or arbitrary constructor.

This slice implements immutable FactSource, ApplyStepSource and FactSourceFingerprint
in the neutral contracts package, plus stable fingerprint extraction and a clearly
named runtime SHAPE validator. It does not implement generation authority, producer
admission, verified HA principals, source redaction or full HouseFact construction.
A well-shaped source is not authorization. Future adapters must assign/reassign kind,
registered identity, active configuration fingerprint and actor from verified inputs;
never call this shape validator as their sole authority check. Fabricated admin data
can be structurally valid and must still be rejected by that future boundary.

Use the exact specified closed fact/action/actor vocabularies. The action shape omits
route_fingerprint and excludes fact-only/legacy kinds. Both shapes keep the UUID safety
net specified for tests/tooling; callers in production must supply an origin-minted
correlation_id explicitly and propagate it unchanged. Stable fingerprints exclude
correlation_id but preserve kind/id/type/actor/configuration/route exactly. No new
fingerprint syntax or normalization: they are opaque strings assigned by their owner.
Only string/optional-string SHAPE is checked here; registered IDs and causal-origin
semantics require the future owning boundary. No new empty-string/length/digest-format
rule is assigned to fields the owning source contract declares only as str.

Runtime shape admission always excludes legacy; production mode excludes kind=test
or actor=test. Explicit test_mode allows test shapes only for the isolated harness;
it does not authorize anything. Archival FactSource values can still represent legacy,
as the normative vocabulary requires. Diagnostic errors are fixed prose and do not
echo source content. There is no actor_ref/person/service identity field, arbitrary
payload, hidden authority token or second provenance envelope.

Planned five-method evidence: exact vocabularies and fact/action distinction;
kind=test × actor=test × test_mode, legacy independent of mode; optional strings
None/empty/nonempty, wrong primitive/Enum types; MC/DC isolates kind and actor test
conditions; PBT correlation invariance and individual stable-field sensitivity;
fresh scoped mutmut plus frozen/slots and semantic field-inclusion supplements.


## Final evidence and limits

169 focused instances; full V3 **1243 passed**, seed3145. Exact fact/action/actor
vocabulary fixtures are independent of production aliases; all fact-only kinds
are rejected on the action side. Runtime data-mode table covers kind=test ×
actor=test × test_mode for both shapes, with independent legacy-mode and default-
production checks. Optional strings None/empty/nonempty and primitive/Enum type
boundaries are tested without adding registry/digest/length rules. Defaults match
the owning dataclass schemas; explicit causal propagation does not invoke UUID4.

MC/DC isolates kind=test and actor=test under production mode, and toggles mode
at fixed test data. The optional-text helper is exercised with None/optional on,
None/required, and invalid primitive/optional on. Each stable field independently
changes the fingerprint; correlation changes do not. Two seeded properties check
correlation invariance and separate configuration/route sensitivity. Shape guards
revalidate forged instances and explicitly call base validators rather than a
subclass's overridden hook. Three bypass regressions first failed, then passed.

No extra dataclass fields or live mutable source payloads are retained. Structured
source/fingerprint projections have exactly their specified fields. Error messages
do not echo field data. This verifies shape, not removal of secrets embedded in
arbitrary strings: future trusted owners must assign/redact registered IDs and
metadata before storage/diagnostics. A well-shaped fabricated admin source still
has no authorization; an explicit test documents this boundary rather than making
a fake authority claim.

Ruff lint/format69files,mypy28sources,diff check pass. Fresh mutmut134generated,
106killed,28individually reviewed generic-prose equivalents; zero error/timeout/
skipped/untested/interrupted. Eighteen supplements killed with clean169-test
baseline (all three type frozen/slots flags, three closed vocabularies, nine public
defaults). See FACT_SOURCE_MUTANTS.md for exact diffs, initial test gap and rerun.
No verified HA ingress, composed-generation binding, producer authority, redaction
adapter, Provenance, full HouseFact, fact/marker SQL or live deployment is complete.
