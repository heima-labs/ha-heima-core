# V3 implementation worktree

This worktree is for implementing Heima V3 on branch `feat/v3-implementation`. It is separate from the V2 runtime and from the V3 specification worktree. Do not treat the V2 code as the V3 contract.

## Read at the start of every task or resumed session

1. Read `docs/v3/WORKING_CONTEXT.md` for the last verified state, decisions, current task, and next step.
2. Read `docs/v3/DEVELOPMENT_POLICY.md` for development, test, Git, and deployment rules.
3. Read `docs/v3/RESUME_PROMPT.md` when resuming from another chat or a compacted context.
4. For the specific behavior being implemented, read the *current working copy* in `../ha-heima-component-v3-planning`: first `AGENTS.md`, `docs/specs/v3/contract_registry.json`, and `docs/specs/v3/spec_workflow.md`, then the owning Layer 0–5 contract and its dependency closure. The planning worktree has uncommitted changes that are absent from this branch's checkout. Its layer specs are authoritative; its recap and architecture overview are orientation; its backlog records decisions and open issues.

Before acting, compare this worktree's Git status with the context file. If they disagree, inspect the files and report the mismatch rather than assuming the context is current. Keep implementation design choices distinguishable from approved specification decisions. Do not invent definitive behavior for an open CA4 issue. When a task ends or is interrupted, update `docs/v3/WORKING_CONTEXT.md` with completed work, changed files, tests and results, unresolved decisions, and the exact next action. Keep it concise and factual; do not claim a test ran when it did not.

Use the policy file for task workflow. Never deploy V3 to an existing V2 instance or publish/merge it as a side effect of a coding task.
