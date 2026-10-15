# HouseFact construction — impact and implementation choices

Planning aa4455a clean/read-only; read L1 §3/§4/§5 and §10, L0 §5 and source
fingerprint §4.0, registry L1-HOUSE-FACT-TIME/EVIDENCE-INSTANT/NUMERIC-DOMAIN and
L0-FACT-SOURCE. Preserve prior uncommitted CA4-104 documentation; no Topology work.

Implement the approved one public build_house_fact entry point assembling exactly
HouseFact(fact_type,value,where,when,how) and Provenance(confidence,source,available,
evidence), with FactBuildResult(fact,diagnostics). Essential invalid inputs reject;
invalid supporting evidence is dropped with an existing bounded PayloadDiagnostic.
Reuse freeze_house_fact_value/prepare_evidence; no duplicate payload validator,
confidence formula, HA call, event emission, logging, I/O or implicit clock.

Construction choice: HouseFact/Provenance are frozen/slots output records whose
ordinary constructors reject and direct callers to the builder. This enforces the
approved single entry point without dropping fail-soft diagnostics on another path.
Internal assembly accepts only locally prepared values; the records expose exactly
the specified fields, not PreparedPayload wrappers or hidden diagnostic fields.
FactBuildResult is local construction metadata, not a persisted envelope. Constructor
and error-type details were left as implementation choices in the approved API note.

Use primitive non-boolean confidence numbers in [0,1], no numeric coercion; None iff
unavailable. Integer0/1 meet Python's float annotation and the quantitative numeric
rule; preserve them. Even unavailable values still obey payload shape/size/domain;
their semantic value stays undefined and is neither forced to None nor usable by
consumers. Missing evidence uses a private omission sentinel so explicit None remains
an invalid mapping and emits the prescribed diagnostic. Raw input is never retained.

Copy validated Location/source fields to concrete owned records, preserving opaque
IDs and correlation. Validate canonical encodability of essential metadata through
the existing RFC8785 codec (lone surrogates reject). Source mode uses the existing
validate_runtime_source_shape policy: default production excludes test kind/actor;
explicit isolated test_mode permits them; legacy always rejects. Shape is not source
authorization: trusted producer/generation/verified HA ingress and redaction remain
required before runtime admission. Do not invent an unknown-source sentinel/kind.

Provide canonical fact bytes for comparison/storage: the five fact fields, where
projected as Location's four declared fields with code-point-sorted room_ids, and
how as its four fields. No LocationKey/AppendOrder/authority flag is added to the fact.
The LocationKey scalar text codec remains the separate follow-up-subject contract.
Full record/provenance equality+hash use shared canonical bytes, so True differs from
1 while 1/1.0 and signed zeros compare canonically. This is not state write-on-change:
that future fingerprint excludes time/correlation/evidence and canonicalizes unusable
value, as L0 §4.0 requires. No extra canonical byte cache/duplicate payload is retained.

Planned testing: availability/confidence/source-mode/evidence decision tables;
confidence below/at/above0/1, nonfinite/bool and inconsistent pairs; value/evidence
8KiB boundaries, depth/numeric rules and mutable-input detachment; MC/DC on changed
compound predicates; PBT canonical equality/immutability/evidence degradation;
fresh scoped mutmut plus frozen/slots/omission/semantic field supplements.


## Final evidence

110 focused instances; full V3 **1362 passed**,seed3145. Decision tables cover
availability/confidence pairs, hard value failure for available/unavailable facts,
evidence failure modes, source test/production modes and mandatory fields. BVA
includes nextafter boundaries around0/1, signed zero, subnormals, nonfinite and
large integers without overflow; value/evidence canonical sizes8191/8192/8193;
empty/malformed dotted names, invalid/UTC-only instants, Unicode and all Location
forms. Exact source fields/correlation survive copying; source UUID safety net is
never invoked in the builder. Frozen record values retain type with detached fields.

MC/DC: wildcard-present versus valid identifier at fixed nonempty segments; empty
segment versus valid identifier at fixed no wildcard. Available=True/confidence=None
versus True/0 isolates presence, and True/0 versus False/0 isolates availability.
Finite negative-ulp/zero isolates the lower range comparison with the upper true;
one/nextafter(1,+inf) isolates the upper with lower true. Evidence omitted and
explicit None exercise the independent omission branch. Reuse source-mode helper's
existing table; this slice propagates mode unchanged rather than recoding policy.
Two seeded PBTs assert input-mutation invariance and evidence-only degradation
preserving every essential field. Canonical equality/hash fixtures distinguish
booleans/numbers while equating1/1.0 and signed zeros. Full record time/evidence
changes remain visible; no write-on-change fingerprint is implemented here.

Ruff lint/format73files,mypy29sources,diff check pass. Fresh mutation233generated,
189killed,44reviewed generic-prose equivalents; zero errors/timeouts/skipped/untested/
interrupted. Eleven semantic supplements killed, with clean110-test baseline. Initial
Provenance hash test gap was corrected and the run restarted; see companion report.
No new dependency, policy, Topology implementation or planning edit. Prior uncommitted
CA4-104 notes retained. Diagnostics must be emitted by future runtime admission;
registered source authority/redaction, typed producer value semantics, full fact
text decoding, FactIdentityKey/change-fingerprint owner, accepted append metadata,
SQL batch/marker and HA lifecycle remain future work. Canonical whole-fact bytes
are an encoding API for builder outputs, not untrusted-input validation or a sandbox.
