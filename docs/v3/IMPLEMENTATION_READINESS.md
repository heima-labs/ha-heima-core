# V3 implementation readiness — 2026-10-13

This is a scoped readiness audit, not a new development policy or an approval of tools.
The authoritative planning correction is commit `f84d4e7`; recheck later planning commits
before implementing a specific contract.

## Result and evidence

No open CA4 correction blocks a narrow pure Layer-0/1 contract slice. The planning checker
reports 7 authoritative layer files, 114 mapped contracts, 78 CA4 issues, 0 open and 54
reviewed slices. That establishes the tracked specification status and structural map,
not a proof that every V3 behavior is implemented or free of undiscovered contradictions.

The empty V3 package skeleton and test directory guide now exist in this checkout; no behavioral code/tests exist yet. Its approved
package boundary is `custom_components/heima/v3/` with contracts, runtime, storage and HA
adapters. Planning copies in this checkout are older; use the current sibling planning
worktree and a reviewed commit reference instead of trusting these old copies.

## Before the first behavioral code slice

- Agree a small slice and its concrete module/API boundaries. A possible first slice is
  canonical instants, Location, FactSource/Provenance and immutable HouseFact construction
  and payload validation. This is a proposal, not an authorization to implement all of them.
- **Environment completed on 2026-10-13:** dedicated `.venv-v3` on workspace-local
  CPython 3.14.5 arm64 for Apple M1, with hashed pinned dependencies and dedicated
  pytest/Ruff/mypy configs. The inherited Python 3.13/HA 2025.1.0 V2 configuration
  has been removed from this worktree; the V3 HA integration release/harness is selected later.
  See `TEST_ENVIRONMENT.md` for reproduction and actual local probe results.
- **Initial toolchain verified:** pytest/pytest-asyncio/pytest-cov, Hypothesis,
  mutmut, Ruff and mypy. Temporary decisions/boundaries/properties/async probes passed
  and all 3 generated mutants were killed. Decision Tables and MC/DC still require
  behavior-derived evidence for each actual code slice; coverage is not MC/DC.
  Numerical thresholds remain undecided.
- Import isolation prepared: the user approved building V3 from scratch. The parent
  initializer and approved package groups are inert; pure imports execute neither HA
  nor V2. No test namespace shim is used. Preserve this boundary when adding the HA adapter.
- Implement canonical validation/serialization to the owning contracts. Payload size,
  collection depth, finite-number rules, immutable copying and canonical fingerprints
  are already specified; library/module selection is an implementation decision.

## Before storage implementation

SQLite, a local serialized writer, required atomic transaction units and WAL with
`synchronous=FULL` are approved as a starting design. Missing concrete work:

- SQL tables/indexes, schema versioning for V3, and database path;
- worker/thread/async boundary, bounded queue representation and acknowledgement API;
- persisted per-key baseline validity and global invalidation/closure metadata;
- recovery capacity/fairness, ordering, restart and shutdown/drain mechanics;
- checkpoint/backup cadence and failure/crash/performance verification.

CA4-38/70 already define product behavior; none of these choices permits replacing the
approved queue loss or progressive recovery rules. Verify the SQLite runtime linked to
the eventual target before choosing release-dependent behavior.

## Later gates

- Scheduler/clock implementation and HA lifecycle/intake/service adapters before their
  runtime slices. A pure contract slice does not need a running HA instance.
- Distinct V3 HA lab, deploy target and rollback procedure before live verification;
  deployment policies are still proposals pending developer review.
- Git workflow decisions remain proposed. The developer explicitly authorized the local
  commits in this task; that does not approve merge, push, deploy or all proposed rules.
- Layer 7/8 completion and CT-4 numerical release evidence are later requirements, not
  blanket prerequisites for the pure Layer-0/1 foundation.

## Validation of this audit task

Reviewed only the owned pending changes before explicit-path staging. Planning
`scripts/check_v3_specs.py` and patch hygiene checks pass. No V3 runtime, behavioral, crash, performance or live test ran. The subsequent
environment task ran temporary test/property/mutation probes outside the repository;
those results validate the tooling and are documented in `TEST_ENVIRONMENT.md`.
