# V3 implementation policy

Status: working policy for this implementation worktree. Change it explicitly when the developer decides differently; record the decision in `WORKING_CONTEXT.md`.

## Sources and scope

- The current Layer 0–5 specifications in `../ha-heima-component-v3-planning/docs/specs/v3/` own planned behavior. Read only the relevant owning contract and dependency closure for each slice. The registry is a navigation map, not a substitute for the normative text. The backlog distinguishes approved decisions from open CA4 issues.
- Keep V3 code isolated from the V2 runtime until an explicit integration/cutover decision. Do not alter V2 behavior, active V2 specs, or production data as an incidental part of V3 work. V3 is a clean start; do not create a V2 migration path without a new product decision.
- Treat package/module names, database, schema, concurrency design, and HA adapters as implementation decisions. Record their rationale and rejected alternatives before making a costly choice. Reuse a V2 mechanism only after checking it against V3 semantics.
- Design the Layer 0/1 foundation as pure immutable contracts plus runtime services. Avoid a behavioral import cycle. Keep HA objects and I/O outside pure value construction and the per-cycle hot path. Do not freeze an interface whose meaning depends on an open CA4 issue; a narrow prototype may be marked experimental.

## Work sequence

1. State the bounded task, owning spec sections, dependencies, open issues, acceptance behavior, and expected files. Update the current-task field in `WORKING_CONTEXT.md`.
2. Implement one reviewable vertical slice. If the spec is contradictory or requires an unapproved product choice, stop that dependent behavior, record the exact case, and continue independent work. Do not silently decide a product rule in code.
3. Add tests for the changed behavior and meaningful boundary cases. Keep pure contracts and storage adapters independently testable. Use fake clocks and temporary stores for time/persistence; cover unavailable input, restart, retry, failure, and concurrency where relevant.
4. Run focused tests first. Before declaring a slice ready, run appropriate lint/format/type checks and `bash scripts/ci_local.sh` when the V3 slice is integrated with the component. Run `python3 scripts/check_v3_specs.py` in the planning worktree only when changing specs there. Record commands, outcomes, and unrun gates separately.
5. Review the diff against the owning contract and acceptance criteria; run `git diff --check`; update `WORKING_CONTEXT.md`.

Do not use a green structural check as proof of semantic behavior. Do not add tests that only mirror an implementation detail. Escalate testing only for a concrete remaining risk.

## Git

- Use only `feat/v3-implementation` and short task branches from it for V3 code. Inspect `git status` before edits. Preserve unrelated local changes; do not reset, clean, or overwrite them.
- Keep commits scoped and reviewable, with English messages and DCO sign-off (`git commit -s`), consistent with `CONTRIBUTING.md`. Commit only after the slice and its context update are coherent. Never commit secrets, HA tokens, observability dumps, runtime databases, or generated caches.
- Do not merge, rebase onto an updated source, push, or open a PR as an implicit part of an implementation task. Do so when explicitly requested, after reporting the exact branch, diff, and test evidence. Never copy uncommitted planning specs into this branch as an opaque bulk change; coordinate a reviewed spec commit or a bounded, traceable sync when needed.

## Deploy and live tests

- Default verification is local and isolated. V3 must not use the existing V2 production or shared development instance for deployment or mutation. Set up a distinct V3 HA test instance/config and data directory before any live V3 test.
- Before deployment, identify the exact target, version/commit, data path, expected effect, rollback method, and completed local checks. Obtain explicit authorization for that target as the final step unless the user has already authorized it in the session. Do not run the V2 `scripts/deploy_heima.sh` for V3 without a reviewed V3 target mode.
- A live test records its target and result; a local unit test is never described as live evidence. A successful deployment is not evidence that a scenario passed.

## Decisions still requiring implementation design

Select and document the package boundary, durable store and transaction layout, queue worker and overflow policy, clock/scheduler adapter, canonical serialization implementation, HA lifecycle adapter, and V3 test lab. Check the live CA4 queue before fixing any of these: CA4-20, CA4-28, CA4-38 and CA4-54 directly affect the foundation. These are prompts for design work, not preapproved technology choices.
