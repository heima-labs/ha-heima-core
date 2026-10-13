# Heima V3 implementation

This worktree builds Heima V3 from scratch. The package skeleton is present;
application behavior and the Home Assistant lifecycle adapter are not implemented.
This checkout is not an installable Home Assistant integration yet: there is no
V3 manifest, config flow or deployment workflow.

Start with [AGENTS.md](AGENTS.md) and [working context](docs/v3/WORKING_CONTEXT.md).
Use the current specifications in `../ha-heima-component-v3-planning`; inherited
specification copies and V2 documentation here are historical reference.

## Development

Use the native Python 3.14.5 environment and pinned tools documented in
[TEST_ENVIRONMENT.md](docs/v3/TEST_ENVIRONMENT.md), with `pytest-v3.ini`,
`ruff-v3.toml` and `mypy-v3.ini`. No V3 behavioral test exists yet.
Git and deployment policies still await review. The inherited V2 CI, tests and
operational scripts have been removed from this branch; a V3 CI and deploy target
will be designed separately.

V2 remains in `../ha-heima-component` and Git history. Do not import its runtime,
configuration, stores or learning into V3. Small pure functions may be reused only
after checking their semantics and dependencies against the V3 contract.
