# V3 code rules

These rules expand the mandatory principles in root `AGENTS.md`. They govern code changes in this V3 worktree. The live Layer 0–6 specs in the planning worktree own product behavior; this file does not add new V3 behavior. The existing `CONTRIBUTING.md` supplies English language and Ruff conventions. The approved five-method testing requirement lives in `DEVELOPMENT_POLICY.md`.

## Understand and preserve contracts

Before changing implementation, trace the affected behavior through callers, consumers, stored state, existing tests, and downstream effects. Compare code, tests, and documentation as evidence; do not assume that any one of them is automatically correct when they disagree. Identify the owning specification and the exact externally observable contract. Expose an incomplete or contradictory requirement instead of choosing silently.

Keep framework code at the boundary. Domain calculations should take explicit, typed inputs and return explicit outputs. Keep Home Assistant `State`, `Entity`, `ConfigEntry`, `DataUpdateCoordinator`, service calls, and other framework objects out of domain logic where practical. Concentrate I/O, network, filesystem access, Home Assistant access, and mutation in named boundary components. Do not introduce blocking file access, synchronous HTTP, `time.sleep()`, or heavy CPU work into Home Assistant's async event loop.

Make configuration, clock, cache, state, and dependencies visible at construction or call sites. Avoid mutable global state, implicit singletons, and ambient dependencies. Prefer pure deterministic functions for domain decisions. Use dataclasses, enums, `StrEnum`, `TypedDict`, `Protocol`, and type aliases where they express real domain constraints; avoid indiscriminate `dict[str, Any]`, free-form strings, or anonymous records. A specification-defined generic field such as `HouseFact.value` remains valid only with its specified validator and shape constraints.

Separate mechanisms from thresholds, weights, and policy decisions. Give each rule one authoritative owner. Use the smallest **correct** change: preserve behavior and contracts, even when doing so takes more lines than the smallest diff.

## Pragmatic design principles

- **Single responsibility:** give each module, class, and function an identifiable purpose. Split only when it improves understanding or testability.
- **Open/closed:** prefer a localized extension over repeated edits to stable central code when that reduces risk; do not create a framework for a single hypothetical extension.
- **Liskov substitution:** an implementation or subtype must preserve the full input, output, error, and state-transition contract of the type it replaces.
- **Interface segregation:** expose the narrow capabilities each consumer needs; avoid forcing a consumer to depend on unused methods or state.
- **Dependency inversion:** keep high-level domain logic independent of Home Assistant, I/O, and concrete storage implementations where this avoids coupling.
- **DRY:** deduplicate domain knowledge and policy rules, not merely similar syntax. Temporary duplication is preferable to an abstraction that joins semantically different behavior.

Use names from the domain. Prefer focused functions and readable control flow; reduce deep nesting and use guard clauses when they clarify intent. Make Boolean meanings explicit; replace unexplained numeric and string literals with named domain concepts. Avoid generic `Manager`, `Helper`, `Utils`, `Data`, and `Info` names when a precise concept exists. Comment why a non-obvious rule exists, not a line-by-line description of what the code does. Represent errors, degraded states, and valid absence of evidence explicitly. Prefer composition to inheritance without a strong “is-a” relationship. Avoid premature optimization and premature abstraction. Favor readability, determinism, testability, and observability.

## Errors, refactoring, and public boundaries

Catch the narrowest useful exception and handle it visibly; never use `except Exception: pass`. Distinguish technical failures from valid domain results such as insufficient data, no valid candidate, or low confidence. A refactor preserves observable behavior unless the task expressly changes it. If a feature or fix requires broad refactoring, limit the necessary edit or surface a separate task.

V3 starts clean: do not migrate V2 configuration, history, runtime state, or learning into V3. Once a V3 public contract exists, treat changes to it as potentially breaking and assess them explicitly. Review `unique_id`, entity and device identifiers, entity semantics, config-entry data/options, V3 migration schemas, states, attributes, services/actions, diagnostics, and saved data before changing them. Record the affected consumers and the compatibility or cutover decision; never add V2 compatibility implicitly.

## Verification evidence

Each test must exercise a specified behavior, requirement, invariant, boundary, error condition, state transition, regression, or meaningful property. Coverage percentage is not the primary objective; do not add tests solely to execute uncovered lines. For a bug fix, demonstrate the new regression test failing on the previous implementation for the expected reason before applying the fix. Follow all five testing techniques in `DEVELOPMENT_POLICY.md` for changed code; the attachment's “when available and relevant” wording does not weaken the user's earlier explicit requirement.

Before reporting completion, inspect the diff for unrelated changes; run focused tests, the relevant suite, lint, type checking, format check, and pertinent Home Assistant integration tests. Report each result and any unavailable validation. Do not claim a structural check or coverage percentage proves contract behavior.
