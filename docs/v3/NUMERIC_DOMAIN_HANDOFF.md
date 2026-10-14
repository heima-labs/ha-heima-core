# Approved numeric domain — specification handoff

Status: approved by the developer on 2026-10-13; incorporated by Claude in planning
`15ccdcd` (CA4-96) and verified on 2026-10-14, worktree clean. Layer 1 §§3/4/4.3/10
own the rule; Layer 0 §4.1 and Layer 5 §6.0 reference it. No discrepancy found.
This note retains the decision record; no further handoff is pending. Codex keeps
the planning worktree read-only.
No serializer library, code slice or implementation is approved by this note.

## Incorporated decision

Applies recursively to `EvidenceValue`-shaped payloads: HouseFact.value,
Provenance.evidence, fields of permitted frozen dataclass values, and
PersistedProjection. Configuration has its own owning contracts and limits.

- Non-boolean `int`: inclusive range `[-9007199254740991, 9007199254740991]`,
  equivalently `[-(2**53-1), 2**53-1]`. Integers outside it are rejected, never
  implicitly converted to float or string. This is Heima's explicit safe-integer
  policy, narrower than all exactly representable binary64 integers permitted by JCS.
- `float`: finite binary64 values, including subnormals; reject NaN and infinities.
  No generic physical-range bound or fixed decimal rounding. Floating-point values
  do not promise exact decimal arithmetic or exact arbitrary-size counters.
- `bool`: remains a valid boolean payload, rejected wherever a quantitative number
  is required.
- Decimal, Fraction and complex objects are not generic numeric payloads. Numeric
  strings remain strings; no implicit coercion. Exact large integers or decimals
  require a separately declared string encoding/schema if a real use case needs one.
- JCS canonicalizes 1 and 1.0 identically, and both signed zeros to 0. Stricter
  owning contracts (including negative-zero rejection) still apply.
- Specific field ranges, units, count semantics and confidence constraints remain.
- Invalid value: hard construction failure. Invalid evidence: empty evidence plus
  diagnostic, retaining the otherwise valid fact.

## Owning specification / impact

Primary owner: Layer 1 §3 Numeric scalar rule and §4 EvidenceValue /
PersistedProjection; reconcile §4.3 evidence violation policy and §10 acceptance
criteria. Check dependent projections and canonical scalar facet codecs against
this common numeric domain. Do not change state identity, write-on-change, queue
or recovery mechanisms. Update registry/review/backlog/orientation only as required
by the planning workflow; do not invent an issue number in advance.

Acceptance examples should cover inclusive integer limits and the next values
outside each limit, booleans in numeric fields, finite/subnormal floats, NaN and
infinities inside nested collections/dataclass fields, negative-zero behavior
under generic versus stricter contracts, and value/evidence failure distinction.
These are proposed specification scenarios, not executed behavioral tests.

RFC 8785 remains the canonical rule. CBOR remains a possible future alternative
if measured performance problems justify evaluation; no automatic codec switch.
The Trail of Bits rfc8785 integer policy matches this decision, but exact library
version and conformance verification remain implementation work.
