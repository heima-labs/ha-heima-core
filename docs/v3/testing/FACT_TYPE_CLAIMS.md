# Fact-type claims — impact before implementation

Parent1c8adbe. Planningaa4455a clean/read-only. Owning L0 §4 emission semantics,
claim grammar and overlap admission, §13; L1 §3 concrete fact identifiers.
Reuse existing canonical encoder and keep HouseFact exactly five fields.

Bounded slice: FactEmissionKind/FactTypeClaim and pure staging-only grammar,
matching, overlap/conflict validation. Refactor the existing builder's concrete
name check to one shared validator without changing accepted names or failure
semantics. No producer capability, source-authority proof, full reserved-core
composition, static (type,Location) claims, live registry, coordinator or SQL.

Implementation choice: dotted segments checked independently; finite product
of wildcard automata. Epsilon edges skip stars; consuming edges match
literal/literal or wildcard. A common empty witness is possible only for two
all-star segments, which also share any one non-dot literal, so no false empty
segment witness is admitted. Segment counts must
agree. No regex/fnmatch semantics (question marks/brackets/backslashes are literal),
no recursive call stack, no wildcard across dots. State-space bound quadratic in
segment lengths, staging only. No new dependency or pattern-length policy.

Decision table: overlap/no overlap × same/different owner × same/different kind;
only overlapping claims with unequal owner or kind reject. Patterns with only
stars still require a nonempty concrete segment. BVA empty segments, zero/one
wildcard matches, adjacent stars, segment-count differences, metachar literals,
opaque Unicode and repeated long patterns. MC/DC isolates each compatibility,
terminal and conflict condition. PBT symmetry/self overlap, generated concrete
witnesses, finite exhaustive language oracle for short patterns over{a,b,*}.
Fresh mutation for new module and touched builder, semantic decorator supplements.
## Final evidence

91 new focused cases plus110 existing builder cases (201 focused); full V3
1504 passed, seed3145. Ruff lint/format79files,mypy31sources and diff check pass.
New module enters permanent mutation scope25modules; no dependency/policy change.

Decision table: eight rows cover overlap × same owner × same emission kind.
Different namespaces/segment counts do not conflict; matching owner/kind overlaps
are accepted, including duplicate claims. A third conflicting claim is checked
after both unrelated and equivalent first pairs. State/event fields remain
configuration metadata, never HouseFact fields. Full core reserved claims are
not assembled by this helper; future composition must supply them.

BVA: empty identifier/leading/trailing/doubled dot; zero/one/many wildcard
characters; adjacent stars; minimum one concrete code point; different segment
counts; literal ?,brackets,backslash; Unicode case/normalization differences;
1500-character literal prefixes (no recursion). No invented length/owner-id limits.

MC/DC pairs for introduced compound decisions:
- owner equality and emission equality: (same,same) versus (different,same),
  and (same,same) versus (same,different), at fixed overlapping patterns.
- terminal coordinates: (end,end), (end,not-end), (not-end,end) reached by
  a/a, a/a*, a*/a boundary paths; epsilon edges finish the remaining star.
- exhausted-input OR: (end,star) and (star,end), versus two available tokens;
  guarded finite-product fixtures expose either missing independent check.
- transition compatibility OR: star/literal, literal/star and equal literals
  each permit consumption against unequal non-star literals as false baseline.
  Complete matching/overlap tables and generated witnesses exercise both sides.
- conjunction across segments: x.a.y equal versus a mismatch in each of the
  first/middle/last positions; empty segment any-check similarly varied by position.
Six explicit post-campaign probes also executed the exact a/a, a/b, */a,
a/*, a/a*, a*/a pairs above (True,False,True,True,True,True). These reach the
terminal and transition boundary states in addition to the permanent tables.
Single predicates (vocabulary/type/visited/length) have direct decision rows.
The finite-product guard is a test of termination/state-domain invariants, not a
hardware-dependent latency gate. All-star/all-star intersections have nonempty
witnesses even though epsilon paths can also accept empty internally.

Three seeded PBTs: an independent finite-language expansion oracle for short
patterns, explicit common concrete witnesses, and self-overlap/equivalent-owner
composition. Oracle enumerates1..6-length words over{a,b} for <=3-token patterns;
any common witness needs at most both literal subsequences plus a nonempty symbol.
It does not use production glob functions to construct its expected intersection.

Fresh scoped mutmut includes fact_types.py and refactored house_facts.py:
380 generated,302 killed,75 reviewed equivalents (72 error prose,3 zip-strict),
3 timeout defects killed separately by exact-diff finite-product supplements.
No errors/skipped/untested/interrupted. Initial campaign exposed a continue→break
test gap, fixed before a fresh full rerun. Report FACT_TYPE_CLAIM_MUTANTS.md retains
all survivor/timeout diffs and the post-campaign supplemental test addition.
Five claim supplements and11 existing builder supplements killed after clean
baselines; collection/no-selection or passing mutant results are not counted.

Concrete-name validation moved from the builder into validate_fact_type; accepted
names and error classes remain unchanged, only generic exception wording may vary.
No persisted schema, HA public API, source authority or V2 behavior changed.
No actual producer port/admission/index/queue/SQL/HA integration or ARM benchmark
is implemented or implied by these pure staging tests.
