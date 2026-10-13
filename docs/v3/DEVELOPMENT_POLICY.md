# V3 implementation policy

Status: mixed. The user approved the five-method testing requirement and the contract-preserving code rules in `CODE_RULES.md`. The Git and deployment sections below are proposals awaiting developer review; they are not binding merely by appearing here. Source-of-truth statements reflect the V3 specifications. Record new decisions in `WORKING_CONTEXT.md`.

## Sources and scope

- The current Layer 0–6 specifications in `../ha-heima-component-v3-planning/docs/specs/v3/` own planned behavior. Read only the relevant owning contract and dependency closure for each slice. The registry is a navigation map, not a substitute for the normative text. The backlog distinguishes approved decisions from open CA4 issues.
- Keep V3 code isolated from the V2 runtime until an explicit integration/cutover decision. Do not alter V2 behavior, active V2 specs, or production data as an incidental part of V3 work. V3 is a clean start; do not create a V2 migration path without a new product decision.
- The approved package boundary is `custom_components/heima/v3/`, with `contracts/`, `runtime/`, `storage/`, and `adapters/ha/`. SQLite is the approved V3 persistence engine. Approved starting design: one local serialized writer outside the HA event loop, the agreed atomic transaction units, WAL with `synchronous=FULL`, and SQLite backup API. Individual module names, SQL schema, concrete worker, checkpoint cadence and HA adapter details remain to be resolved. Record their rationale and rejected alternatives before making a costly choice. Reuse a V2 mechanism only after checking it against V3 semantics.
- Design the Layer 0/1 foundation as pure immutable contracts plus runtime services. Avoid a behavioral import cycle. Keep HA objects and I/O outside pure value construction and the per-cycle hot path. Recheck the authoritative specs before fixing an interface; any newly found contradiction belongs in the specification workflow.

## Work sequence

1. State the bounded task, owning spec sections, dependencies, open issues, acceptance behavior, and expected files. Update the current-task field in `WORKING_CONTEXT.md`.
2. Implement one reviewable vertical slice. If the spec is contradictory or requires an unapproved product choice, stop that dependent behavior, record the exact case, and continue independent work. Do not silently decide a product rule in code.
3. For every code change, derive tests from the changed behavior and record evidence for all five required techniques: **Decision Tables**, **Boundary Value Analysis**, **MC/DC**, **Property-Based Testing**, and **Mutation Testing**. A test must be capable of detecting a meaningful defect in the changed code, not merely repeat its implementation. The technique-specific requirements are below.
4. Run focused tests first. Before declaring a slice ready, run appropriate lint/format/type checks and `bash scripts/ci_local.sh` when the V3 slice is integrated with the component. Run `python3 scripts/check_v3_specs.py` in the planning worktree only when changing specs there. Record commands, outcomes, mutation results, and unrun gates separately.
5. Review the diff against the owning contract and acceptance criteria; run `git diff --check`; update `WORKING_CONTEXT.md`.

### Required test design for changed code

- **Decision Tables:** enumerate the relevant conditions, combinations, expected outcomes, and impossible combinations before writing examples. Cover every distinct rule affecting the changed behavior; identify the table rows exercised by tests.
- **Boundary Value Analysis:** exercise values just below, at, and just above each meaningful limit or transition, including empty/maximum shapes and time boundaries where applicable. State why a boundary belongs to the changed contract.
- **MC/DC:** for each compound Boolean decision introduced or changed, demonstrate that each atomic condition independently changes the decision outcome while the other applicable conditions are held fixed. Record the condition/outcome pairs; do not label ordinary branch coverage as MC/DC.
- **Property-Based Testing:** define invariants or relations that should hold across generated valid and invalid inputs, with reproducible seeds and shrinking where the chosen tool supports them. Properties must assert contract behavior, not reimplement the same algorithm as an oracle.
- **Mutation Testing:** mutate the changed code and run the relevant test subset. Investigate surviving non-equivalent mutants and strengthen tests or explain the contract gap before calling the slice ready. Record tool, scope, command, killed/surviving results, and any equivalent-mutant assessment.

If a technique has no applicable construct in a particular code slice (for example, MC/DC when no compound decision exists), record that specific reason in the task's test evidence. Do not silently omit a technique. Tool selection, coverage thresholds, and mutation score gates remain to be agreed with the developer; do not present an arbitrary threshold as approved policy. A green structural check is not proof of semantic behavior.

## Git — proposal pending developer review

- Use only `feat/v3-implementation` and short task branches from it for V3 code. Inspect `git status` before edits. Preserve unrelated local changes; do not reset, clean, or overwrite them.
- Keep commits scoped and reviewable, with English messages and DCO sign-off (`git commit -s`), consistent with `CONTRIBUTING.md`. Commit only after the slice and its context update are coherent. Never commit secrets, HA tokens, observability dumps, runtime databases, or generated caches.
- Do not merge, rebase onto an updated source, push, or open a PR as an implicit part of an implementation task. Do so when explicitly requested, after reporting the exact branch, diff, and test evidence. Never copy uncommitted planning specs into this branch as an opaque bulk change; coordinate a reviewed spec commit or a bounded, traceable sync when needed.

## Deploy and live tests — proposal pending developer review

- Default verification is local and isolated. V3 must not use the existing V2 production or shared development instance for deployment or mutation. Set up a distinct V3 HA test instance/config and data directory before any live V3 test.
- Before deployment, identify the exact target, version/commit, data path, expected effect, rollback method, and completed local checks. Obtain explicit authorization for that target as the final step unless the user has already authorized it in the session. Do not run the V2 `scripts/deploy_heima.sh` for V3 without a reviewed V3 target mode.
- A live test records its target and result; a local unit test is never described as live evidence. A successful deployment is not evidence that a scenario passed.

## Decisions still requiring implementation design

The package boundary, SQLite engine, serialized writer, specified atomic transaction units and WAL/FULL starting design are approved. Concrete schema, queue/worker implementation, checkpoint cadence, scheduler/clock adapter, canonical serializer, HA lifecycle adapter and test tools remain implementation design work. Implement Layer 0's approved overflow and progressive recovery contracts. As checked on 2026-10-13, the planning map has 77 CA4 issues and none open. See `IMPLEMENTATION_READINESS.md` for the scoped audit and distinguish first-contract-slice prerequisites from later storage, integration and deployment work. No new tool, numerical test threshold, Git or deployment policy is approved by this note.
