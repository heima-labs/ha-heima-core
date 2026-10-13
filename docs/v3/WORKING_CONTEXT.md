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
  checked for this task is `64d2105` (clean). Its Layer 0–6 specs supersede this checkout's older copies.
  Layer 6 is now authoritative; later Layer 7/8 design work is separate. Recheck HEAD,
  status and current contracts each session because another session is developing specs.
- Planning structural check passes: 7 layer files, 114 mapped contracts, 78 CA4 issues,
  0 open, 54 reviewed slices. Specification status does not demonstrate runtime behavior.
- The implemented V2 integration and its CI/live scripts remain separate. V3 is a clean
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
Homebrew update. Point 2 is under discussion: propose a pytest-only namespace parent plus a guard against
  HA/V2 imports for pure V3 tests, retaining the approved production package path. This
  proposal is not yet implemented or approved. No V3 application code was written.

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

## Next action

Discuss and agree point 2: a test-only package-parent shim plus an import guard, so
V3 contracts retain their qualified names without executing the V2 parent initializer.
No change to the production parent initializer is proposed at this stage.
Then discuss point 3: the exact first code slice and its modules/APIs. Point 1 is done;
use `.venv-v3` and the dedicated configs/requirements, not the Intel system Python or
V2 dependency pins. HA release/harness selection, concrete queue/writer/schema,
scheduler/clock, test lab and proposed Git/deploy policies remain later work. Do not
implement application code or move to point 3 before the developer's discussion.
