# Fixed-source state producer ports — impact before implementation

Parent47a4dd4 committed and pushed to origin/feat/v3-implementation with tracking.
Planningaa4455a has uncommitted CA4-106 edits (L6/L8 links/registry/backlog); L0/L1
owning text unchanged and read-only. L0 §4/§4.7/§5.1/§5.2, L2 §2.3/§2.5 own
producer claims, generation fencing and assignment of execution-semantic provenance.

Implement runtime/state_producers.py. Trusted core staging registers fixed-source
state producers against composed static declarations, plus source fingerprints
assigned by the owning registry. No caller-supplied HouseFact/source is accepted
by the runtime build method. Kind/identity/actor/config fingerprint come from the
staged profile. Variable-route fusion requires a separate producer port.
when/correlation are explicit inputs from the future cycle coordinator, no UUID.

Prepared generation is immutable staging data, not activation. Explicit active-
generation reader is the runtime coordinator dependency, returning the installed
snapshot only after durable activation and cycle-boundary pointer swap. Identity
comparison fences stale work even for equal manifest IDs. No fake durable receipt,
new controller or persisted trusted flag. Check before and after building a fact
in case a producer payload property reenters and changes the installed snapshot.
Execution is confined to the serialized coordinator thread; no await inside build.

Scope: fixed-source/core-compute state producers. Variable-route fusion, per-edge verified actor/response
source assignment, event ports, future dynamic Layer7 ports and full composition
activation remain separate. Registered subset is explicit; this is not proof that
all layers/producers are implemented. No source profile from untrusted input may
reach this core staging API. Bindings return FactBuildResult including diagnostics,
not an accepted append or durable receipt. No index/queue/order/SQL/live HA yet.

Decision/BVA: missing/wrong-owner/duplicate state registrations, production source
shape, no active/future/current/old generation, same-ID replacement, hard/soft
payload failures and explicit correlation. MC/DC if applicable to new predicates.
PBT source provenance invariant under arbitrary values/causal IDs and stale port
rejection after replacement. Fresh mutmut and immutable-record semantic seeds.
## Verified result — 2026-10-16

22 focused cases; full V3 **1664 passed**, seed3145. Ruff lint/format88files,
mypy34sources and diff check pass. Permanent mutation scope28modules.

Decision table: no active/future/current/old/same-id-different-snapshot generation;
only the captured installed object permits build. Pre-build fence rejects before
payload access. A payload field that reenters and changes the installed reference
is rejected by the post-build fence. New generation receives its staged semantic
fingerprint; old port cannot publish a stale constructed result through this API.

BVA: empty/subset registrations, duplicate claim, wrong owner/type/location,
malformed concrete registration/manifest/composition/source, test/legacy mode,
valid/invalid/omitted evidence, unavailable value/confidence, equal generation IDs.
Every staged source field survives copying; source cannot be overridden by build
keywords. Explicit origin is propagated without UUID minting in stage or runtime.
Mutable registration inputs are owned; map/records/port are immutable. Returned
FactBuildResult preserves bounded diagnostics for future admission to consume.

MC/DC: changed source contains no compound Boolean decision. Each sequential
guard is exercised; pre/post-current checks are separate decisions. Existing
source-mode and payload compound decisions retain their prior five-method evidence.
Two seeded PBTs cover invariant source identity/fingerprint over generated values/
origin IDs and replacement by arbitrary equal/different-ID snapshots. Only these
two functional properties use settings(deadline=None): no latency promise is being
tested, and the default200ms caused a reproduced timing-only FlakyFailure.
Example count, seed and shrinking remain enabled. This is not a global test policy.

Fresh scoped mutmut226generated,161killed,65reviewed equivalents:60prose,3redundant
optional fields in a temporary validation object,2 discarded placeholder variants.
Zero errors/timeouts/skips/untested/interrupted. All12 semantic supplements killed
with clean22-test baseline. Initial campaigns with6/7timeouts discarded after the
clean timing-flake reproducer; final run restarted fresh with corrected tests.
Strengthened no-UUID test exposed and kills a staging-default mutation; production
already supplied its placeholder explicitly. Exact diffs STATE_PRODUCER_PORT_MUTANTS.md.

Explicit runtime-build test poisons pattern matching and composition.resolve_type
after bind: a valid build still succeeds. No pattern lookup or storage I/O enters
this hot path. This does not claim an ARM throughput benchmark or total HA latency.

## Integration contract

Trusted core registry owners prepare coherent manifest/composition/source profiles;
this helper does not derive/check actual semantic digests or prove their origin.
ActiveStateGeneration reader belongs to the serialized runtime coordinator and
returns only the installed snapshot after durable activation/cycle-boundary swap.
Staging/bind never install it. The reader is an explicit trusted dependency, not an
externally supplied generation id or stored trust flag. This component implements
no durable activation transaction or all-layer pointer controller.

Fixed source includes a fixed route and actor. Variable-route fusion, verified
per-edge actor state, authenticated response ingress and events need their own
ports. Layer7 dynamic producers are not implemented. Profile subset is explicit;
preparing it does not prove that all configured layers have executable producers.
Core source redaction and producer-specific value schemas remain owning-boundary
obligations; never deserialize untrusted fingerprints into these registrations.

Build is synchronous on the coordinator thread with no await. Caller supplies
cycle-owned instant and correlation, consumes diagnostics and performs actual
state acceptance in that cycle. The result is not an accepted append, durable
receipt or authorization proof for later asynchronous publication. Current index,
AppendOrder, queue, fact/marker SQL and real HA/bootstrap/activation wiring remain
unimplemented. No V2 migration or new development/Git/deploy policy.

Reproduce with pytest-v3.ini/seed3145, Ruff ruff-v3.toml, mypy mypy-v3.ini;
mutmut run --max-children 4 in fresh isolated scope and mutation_state_producers.py.
