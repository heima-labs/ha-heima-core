# V3 implementation working context

Update this file at the end of every bounded task and before yielding on an unfinished task. Keep only verified current state; move lengthy rationale to a separate decision record when needed. Newer user instructions override the next action below.

## Verified state — 2026-10-06

- Workspace: `ha-heima-component-v3-implementation`; branch: `feat/v3-implementation`, created from committed `feat/v3-planning` at `0063da4`. No V3 implementation code has been written in this worktree yet.
- Authoritative specs: live working copy in sibling `../ha-heima-component-v3-planning`. It has uncommitted changes that are not present in this implementation checkout. Do not use this checkout's spec copies as the current source of truth.
- Last structural spec check: 6 layer files, 39 mapped contracts, 60 CA4 issues, 16 open, 20 reviewed slices. Command: `python3 scripts/check_v3_specs.py --open` in the planning worktree. Re-run for current status; these counts are a dated observation, not a release claim.
- Existing repository contains a V2 Home Assistant integration and local CI/live scripts. V3 code remains isolated. No V3 runtime, V3 unit tests, live tests, or deploy have run.

## Current task

Bootstrap completed: dedicated code worktree and persistent instructions for continuity, development, testing, Git and deployment are present. No implementation technology has been selected by the developer.

## Decisions and boundaries

- User requested a separate V3 implementation workspace and durable prompt/policies.
- Layer 0/1 contracts support an implementation layout, but do not mandate module filenames or a database. An earlier discussion proposed SQLite as a candidate, not an approved choice.
- Open foundation issues include CA4-20 (time ordering), CA4-28 (deep immutability), CA4-38 (queue bounds), CA4-54 (canonical time/duration encoding). Do not implement their disputed behavior as settled.
- The V3 design has a deliberate clean-start cutover; V2 runtime and V3 specs must remain distinct.

## Work done and evidence

- Created worktree from `feat/v3-planning` on `feat/v3-implementation`.
- Added root `AGENTS.md`, this context, a resume prompt, and development policy. Verified all four in the worktree. `git diff --check` passed; no executable test was relevant to this documentation/bootstrap task.
- No test or deployment was performed for this documentation/bootstrap task.

## Next action

Begin a bounded Layer 0/1 implementation design: map exact contracts to modules, compare storage options against the required transactions and history queries, and identify interfaces safe to scaffold before the open CA4 decisions. Record chosen technologies only after that review.
