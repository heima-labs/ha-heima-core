# V3 implementation working context

Update this file at the end of every bounded task and before yielding on an unfinished task.
Keep verified state and distinguish user-approved decisions from proposals. Newer user
instructions override the next action below.

## Verified state — 2026-10-13

- Implementation workspace: `ha-heima-component-v3-implementation`, branch
  `feat/v3-implementation`, branched from planning `0063da4`; the previous instruction commit is `6fe67b8`.
  The current environment/tooling files are included in the developer-requested commit;
  use `git log -1` and status for the latest revision each session.
  No V3 application code, runtime, application tests or deployment exists here.
  The dedicated native Python/test-tool environment is ready; its probes ran in /private/tmp.
- Authoritative specs: sibling `../ha-heima-component-v3-planning`, branch
  `feat/v3-planning`, CA4-70 progressive recovery committed as `f84d4e7`; latest planning HEAD
  checked for this task is `761294d` (clean). Its Layer 0–6 specs supersede this checkout's older copies.
  Layer 6 is now authoritative; later Layer 7/8 design work is separate. Recheck HEAD,
  status and current contracts each session because another session is developing specs.
- Last recorded planning structural check (before `c66afb7`; not rerun for this package task): 7 layer files, 114 mapped contracts, 78 CA4 issues,
  0 open, 54 reviewed slices. Specification status does not demonstrate runtime behavior.
- The inherited V2 component, tests, operational scripts, workflows and obsolete tool configs have been removed from this worktree; V2 remains in its original workspace/history. V3 is a clean
  start with no V2 migration; protect V3 public contracts once introduced.
- CT-4 still has an implementation release gate for frozen numerical calibration and
  reproducible evidence before automatic comfort-trajectory action.
- Previously pending instructions/readiness were committed as `6fe67b8`. The requested
  subsequent environment commit establishes `.venv-v3`/`.python-v3` ignores, the pinned tooling
  requirements, dedicated V3 configs and `TEST_ENVIRONMENT.md`, plus handoff updates.
  Runtime directories are local artifacts, not Git content.

## Current task and approved decisions

The developer requested the three readiness points in order, one at a time. Point 1
is complete: Python 3.14.5 aligned with HA's minimum and running natively arm64 on the
Apple M1; tooling dependencies are pinned with hashes and verified by local probes.
The initial Intel/Rosetta venv was retired to /private/tmp after the user's correction.
The native runtime is workspace-local (uv 0.13.0/CPython standalone), avoiding a global
Homebrew update. Point 2 is now approved and prepared: build the V3 integration
from scratch in this worktree, keeping V2 in its own workspace/history as reference.
Small pure V2 functions may be assessed individually; no V2 runtime dependency.
The approved package groups are empty packages with an inert parent initializer,
so real qualified imports need no test-only namespace shim. No application behavior
or HA lifecycle adapter has been implemented.

- Package boundary approved: `custom_components/heima/v3/` with `contracts/`, `runtime/`,
  `storage/`, `adapters/ha/`. Domain contracts contain no Home Assistant imports. Individual
  classes, filenames and future-layer scaffolding remain undecided.
- SQLite approved, in one local V3 database separate from V2, with one serialized writer
  outside the HA event loop. Approved transaction units: end-of-cycle facts plus
  `CycleCommitMarker`; notification `ready` plus its audit fact; composed configuration
  generation. Qualified `reaction.follow_up` preparation waits for its durable result.
- WAL with `synchronous=FULL` and SQLite's backup API are the agreed starting design,
  subject to performance/crash verification. Schema, checkpoint cadence, queue data
  structures and worker implementation are not yet fixed. Verify the deployment's linked
  SQLite version against SQLite's documented WAL-reset fixes before relying on WAL.
- CA4-38/70: hard queue budget, ordinary superseded-state/event loss order, nonblocking
  admission and one exceptional global `queue_overflow` gap when protected items alone
  cannot fit. Global invalidation does not alter the live current index or short-term buffer.
- Recovery approved on 2026-10-13: fresh valid producer assertions re-seed durable state
  baselines over successive bounded cycle batches. Admission is not acknowledgement.
  The global gap can close at an acknowledged fresh intake/full-cycle accounting boundary
  before all keys recover. Reads requiring unseeded keys stay unknown and incomplete;
  global closure never revives an old invalidated record. Failed/discarded seeds retry on
  a later fresh assertion; further irreducible losses advance baseline invalidation.
- A new HA intake is a current read of HA state, not a forced new device measurement.
  Layer 2's existing `unknown`/`unavailable`/`max_source_age` rules remain authoritative.
  An unavailable producer assertion can establish a durable baseline while that stream
  remains unavailable. Missing durable proof alone does not make the live device unavailable.
- No generic old-state fallback was selected. Desired-target Recovery checkpoints retain
  their existing separate contract. Managed-episode facts require owner proof; a fresh HA
  active reading cannot reconstruct an invalidated opening. Recovery-only unchanged seeds
  do not create live-buffer transitions, physical edges, holds or §4.8 observer deliveries.
- Testing approved: real behavioral verification using Decision Tables, Boundary Value
  Analysis, MC/DC, Property-Based Testing and Mutation Testing. The initial pytest,
  Hypothesis, mutmut, Ruff and mypy toolchain is installed/verified; numerical thresholds
  remain open. `CODE_RULES.md` contains the approved permanent code principles; no V2
  compatibility/migration requirement is implied.
- Git and deployment sections of `DEVELOPMENT_POLICY.md` remain proposals pending review.
  The bootstrap commit does not approve them. No commit, merge, push or deploy is implied.

## Work completed and evidence

- Clean-start preparation: removed 428 tracked V2 files (including the
  replaced parent initializer), added seven inert package initializers and the V3 test
  directory guide; replaced root README and marked inherited CLAUDE instructions historical.
  Kept V3 tooling, instruction files and historical documentation. No CI/deploy replacement
  or manifest was invented. This change is included in the explicitly requested clean-start commit; resolve its revision with `git log -1`. Verification: seven real qualified imports resolve inside this worktree without HA/V2
  modules in `sys.modules`; Ruff lint and format pass; mypy passes on all seven files;
  `git diff --check` passes. No application tests ran. The five behavioral techniques
  have no applicable rule, boundary, compound decision, property or executable function
  to mutate in these docstring-only packages; apply them to the first behavioral slice.

- Workspace/bootstrap, permanent code rules, testing-policy correction and approved module,
  SQLite and transaction decisions are recorded here and in the instruction/decision files.
- Researched bounded queues in Telegraf, OpenTelemetry, Vector and Prometheus and recovery
  patterns in Kubernetes/etcd. Rationale is in `QUEUE_OVERFLOW_DECISION.md`; authoritative
  behavior is owned by planning Layer 0 §§4.0/4.2/4.4/4.6 and the CA4-70 review.
- Updated planning Layer 0, Layer 3 historical consumers, Layer 5 managed-episode validity,
  CA4-70 review, registry/dependencies, backlog, overview and recap. Added scenarios for a
  seed volume above budget, unavailable sources, unchanged seeds, ordered updates,
  repeated overflow, closure with pending keys and crashes before/during/after closure.
- Reviewed §4.8 and Layer 6: notifications observe live committed state, independently of
  durable storage. Their semantics require no modification for this correction.
- `python3 scripts/check_v3_specs.py --issue CA4-70`, `--open` and `git diff --check`
  pass in planning. No V3 runtime, behavioral, crash, performance, CI or live test ran;
  this task changes specifications and instructions only.
- Committed only our eight CA4-70 planning files as `f84d4e7` with DCO sign-off. The
  implementation instruction/audit files are included in the requested separate commit.
  Existing Git/deploy proposals stay unapproved. CA4-69 belongs to the parallel
  specification work and was not edited. Use contextual patches against the latest worktree, avoid whole-file
  overwrites from stale copies, and recheck concurrent changes before writing.

- Environment verification: hash-checked wheel installation and `pip check` passed;
  Python/executable architecture is arm64, version 3.14.5. A temporary probe passed
  9 pytest cases including generated properties and asyncio; Ruff/mypy passed and
  mutmut killed 3/3 mutants. This is tool evidence, not Heima behavior validation.
  Commands, versions and limitations are in `TEST_ENVIRONMENT.md`.

## First behavioral contract — proposal awaiting approval

The user requested the clean-start commit, then agreement on the first contract.
Proposed first slice: `L1-EVIDENCE-INSTANT`, Layer 1 §4 and its §10 acceptance case,
registry dependencies empty, checked at planning `761294d`. No application code yet.
Proposed files: `custom_components/heima/v3/contracts/instants.py`,
`tests/v3/contracts/test_instants.py`, `docs/v3/testing/EVIDENCE_INSTANT.md`.
Proposed API: semantic string type `EvidenceInstant`, strict validation/parsing of
`YYYY-MM-DDTHH:MM:SS.ffffff+00:00`, and explicit formatting from an aware datetime
(normalize its represented instant to UTC; reject a naive datetime). Contract-field
validation accepts only the exact canonical string and never silently repairs input.
Test evidence: validity decision table, date/fraction/offset boundaries, independent
validation-condition pairs where compound decisions exist, generated round trips and
normalization invariants, mutation scope on this module. Exact API names/error types
remain a proposal. This does not implement the cycle clock, scheduler or persistence.

## Next action

Point 2 is complete as a package skeleton. Discuss point 3 next: the exact first
behavioral slice and its modules/APIs. Real qualified package imports are verified;
the HA adapter must preserve this import boundary when it is implemented.
Point 1 is done;
use `.venv-v3` and the dedicated configs/requirements, not the Intel system Python or
V2 dependency pins. HA release/harness selection, concrete queue/writer/schema,
scheduler/clock, test lab and proposed Git/deploy policies remain later work. Do not
implement the proposed first contract before the developer agrees on its scope/API.
