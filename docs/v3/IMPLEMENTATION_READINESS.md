# V3 implementation readiness — 2026-10-13

This is a scoped readiness audit, not a new development policy or an approval of tools.
The authoritative planning correction is commit `f84d4e7`; recheck later planning commits
before implementing a specific contract.

## Result and evidence

No open CA4 correction blocks a narrow pure Layer-0/1 contract slice. The planning checker
reports 7 authoritative layer files, 114 mapped contracts, 77 CA4 issues, 0 open and 53
reviewed slices. That establishes the tracked specification status and structural map,
not a proof that every V3 behavior is implemented or free of undiscovered contradictions.

No V3 package or test directory exists in this implementation checkout. Its approved
package boundary is `custom_components/heima/v3/` with contracts, runtime, storage and HA
adapters. Planning copies in this checkout are older; use the current sibling planning
worktree and a reviewed commit reference instead of trusting these old copies.

## Before the first behavioral code slice

- Agree a small slice and its concrete module/API boundaries. A possible first slice is
  canonical instants, Location, FactSource/Provenance and immutable HouseFact construction
  and payload validation. This is a proposal, not an authorization to implement all of them.
- Establish a reproducible Python/test environment. `pyproject.toml` targets Python 3.13;
  inherited `requirements-dev.txt` pins HA 2025.1.0 and its associated harness. The session's
  `python3` is 3.14.5; no `.venv` is present here. The V3 HA release target remains to be
  decided before HA integration. Do not install the old complete V2 dependency set blindly.
- Choose the concrete tools needed for the approved five testing methods. Existing files
  contain pytest/pytest-cov, Ruff and mypy, but no V3 property-generation or mutation
  configuration. Decision Tables, Boundary Value Analysis and MC/DC need behavioral
  evidence mapped to each changed rule; a branch/line coverage score is insufficient.
  No tool or score threshold was selected by this audit.
- Resolve import isolation for pure tests. Python imports the parent
  `custom_components.heima.__init__`, which currently imports HA and the V2 coordinator.
  A pure V3 test must not initialize that runtime as a side effect. Choose a deliberate
  test/package boundary compatible with the approved directory structure.
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
`scripts/check_v3_specs.py` and patch hygiene checks pass. No V3 runtime, behavioral,
mutation, crash, performance or live test ran: this task changes documentation only.
