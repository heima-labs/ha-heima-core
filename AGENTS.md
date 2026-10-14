# V3 implementation worktree

This worktree is for implementing Heima V3 on branch `feat/v3-implementation`. It is separate from the V2 runtime and from the V3 specification worktree. Do not treat the V2 code as the V3 contract.

## Read at the start of every task or resumed session

1. Read `docs/v3/WORKING_CONTEXT.md` for the last verified state, decisions, current task, and next step.
2. Read `docs/v3/CODE_RULES.md` and `docs/v3/DEVELOPMENT_POLICY.md`. The code and five-method testing rules are approved; Git and deployment sections are proposals pending developer review.
3. Read `docs/v3/RESUME_PROMPT.md` when resuming from another chat or a compacted context.
4. For the specific behavior being implemented, read the *current working copy* in `../ha-heima-component-v3-planning`: first `AGENTS.md`, `docs/specs/v3/contract_registry.json`, and `docs/specs/v3/spec_workflow.md`, then the owning authoritative layer contract (currently Layer 0–6 and Layer 8) and its dependency closure. Check that worktree's Git status and HEAD each session. Its committed specs are currently newer than this branch's checkout; its layer specs are authoritative, its recap and architecture overview are orientation, and its backlog records decisions and issue status.

The V3-planning section of this checkout's `CLAUDE.md` predates the authoritative Layer 0–6 specs and describes historical drafts. Use the current planning worktree for V3 decisions; retain `CLAUDE.md` and `CONTRIBUTING.md` only for applicable repository conventions.

Before acting, compare this worktree's Git status with the context file. If they disagree, inspect the files and report the mismatch rather than assuming the context is current. Keep implementation design choices distinguishable from approved specification decisions. Do not invent definitive behavior for an open CA4 issue. When a task ends or is interrupted, update `docs/v3/WORKING_CONTEXT.md` with completed work, changed files, tests and results, unresolved decisions, and the exact next action. Keep it concise and factual; do not claim a test ran when it did not.

Follow approved rules and the current user instruction. Do not treat a proposed Git/deployment rule as approved merely because it appears in `DEVELOPMENT_POLICY.md`. Do not deploy, publish, or merge as a side effect of a coding task without the required authorization.

## Mandatory development principles

**Codex must not optimize for producing code. It must optimize for preserving contracts.** Contracts include specified behavior, invariants, state semantics, configuration, compatibility, unique IDs, entity semantics, services/actions, attributes, state transitions, and assumptions used by other modules. Apply the detailed [code rules](docs/v3/CODE_RULES.md) alongside the [testing policy](docs/v3/DEVELOPMENT_POLICY.md).

1. Understand current behavior before editing: read the file, callers, consumers, state paths, existing tests, and downstream effects.
2. Treat specifications and documented invariants as authoritative; surface ambiguity, omissions, or contradictions instead of silently inventing behavior.
3. Keep Home Assistant framework objects and operations at adapters; domain logic must depend on explicit domain inputs.
4. Prefer pure, deterministic functions for domain calculations and decisions.
5. Make state, configuration, clocks, caches, and dependencies explicit; avoid mutable globals and hidden singletons.
6. Prefer strong domain types over generic dictionaries, free-form strings, and `Any`, while respecting types expressly defined by the V3 contracts.
7. Separate mechanism from policy; give each domain rule one authoritative source.
8. Require behavioral tests for every behavioral change; for each bug fix, first demonstrate a regression test that fails on the prior code for the expected reason.
9. Test contracts, boundaries, invariants, errors, and state transitions without copying production logic into test oracles; follow the five required test-design techniques in the testing policy.
10. Keep patches focused; do not mix unrelated refactors with features or fixes.
11. Before completion, inspect the diff, run formatting, linting, type checking and relevant tests, and report any validation that could not run.
12. Never change public Home Assistant contracts accidentally; review identifiers, entities, configuration, states, attributes, services/actions, diagnostics, and persisted schemas explicitly.
