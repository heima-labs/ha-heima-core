# Contributing to Heima

Thanks for your interest in Heima. This document explains how to contribute effectively, and — just
as importantly — sets expectations up front so you don't spend time on work that won't fit the
project.

Heima is maintained by a small team (currently a single maintainer). Please read this guide before
opening a PR; it will save both of us time.

## Code of Conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). By participating, you agree to
uphold it.

## Where to ask questions

- **"How do I configure X?" / "Is this expected behavior?" / general support** — use the Heima
  thread on the [Home Assistant Community forum](https://community.home-assistant.io), not GitHub
  Issues. It's better suited to back-and-forth discussion and searchable by other users.
- **Confirmed bugs and concrete feature requests** — use GitHub Issues (templates provided).
- **Code of Conduct concerns** — see [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Ways to contribute

- **Bug reports** — via the GitHub issue template. Attach a diagnostics dump when possible (see
  below); it is almost always the fastest way to get a bug understood and fixed.
- **Bug fixes** — PRs welcome directly, no need to open an issue first for small, well-scoped fixes.
- **Documentation fixes** — typos, unclear steps, outdated references. Always welcome, low risk.
- **New behavior, new domains, or anything that touches the core DAG** — open an issue or start a
  discussion **before** writing code. See "Before you start" below.
- **New external data sources** (weather, civil protection alerts, etc.) — these are **not** added
  to this repo. See "Adding an external adapter" below.

## Before you start: non-trivial changes need alignment first

Heima's core architecture (the domain DAG, the learning/proposal pipeline, the reaction system) is
developed against a living specification (`docs/specs/`) and an operational plan
(`docs/v2_dev_plan.md`). Non-trivial changes — a new domain, a new learning module, a change to an
existing contract — are expected to be discussed against those documents *before* implementation
starts, not after a PR is already written.

Concretely: open an issue describing what you want to add or change and why, and wait for a
maintainer response before investing significant time. This isn't bureaucracy for its own sake — it
avoids two painful outcomes: a PR that duplicates work already planned, or a PR built against an
architectural assumption that doesn't hold.

Small, self-contained bug fixes don't need this — just open the PR.

## The plugin/extension model is closed, for now

Heima does **not** support dynamically loaded third-party plugins. This is not a permanent
technical limitation, but a choice tied to the current complexity of the product: opening an
external plugin API brings attack surface, versioning, compatibility, and support burden that
aren't sustainable today. It's a possibility that will be reevaluated in the future, not a
definitive non-goal. For now, built-in domains and reaction/learning plugins are added by modifying
this repo directly, following the declarative DAG contract described in `docs/specs/heima_v2_spec.md`
and `docs/guides/plugin_authoring.md`.

If you're looking to extend *what Heima can learn or do*, that's a welcome contribution — but it
lands as a PR against this repo, not as an out-of-tree plugin.

## Adding an external adapter

External context sources (weather, regional alerts, etc.) are normalized by dedicated adapter
integrations that live in **separate repositories** under the `heima-labs` GitHub org (e.g.
`ha-heima-owm-adapter`), not in this repo. The contract they must satisfy is defined in
`docs/specs/adapters/external_context_contract.md`. If you want to add a new data source, that spec
is the starting point.

## Development setup

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest -q
```

## What a PR needs to pass

The acceptance bar for an external contribution is the local CI script:

```bash
bash scripts/ci_local.sh
```

This runs the full unit test suite, lint (`ruff`), and format checks. All of it must be green
(`mypy` is informational only and does not block).

Note on test tiers: this repo also has a live end-to-end test suite (`scripts/live_tests/`) that
runs against a dedicated Home Assistant test lab. That lab isn't publicly available, so external
contributors aren't expected to run it — it's a maintainer-side verification step before merging to
`main`. Unit tests (`pytest -q`) are the real bar for a PR to be considered.

## Coding conventions

- Code, comments, docstrings, commit messages, and documentation are written in English.
- Match the existing code style; `ruff` (lint + format) is enforced by CI.
- Don't add tests for behavior you didn't change; do add/update tests for behavior you did.
- Keep PRs scoped to one change. Large, mixed-purpose PRs are harder to review and more likely to
  stall.

## Commit and PR workflow

- Branch from `main`: `feat/<short-description>` for features, `fix/<short-description>` for bug
  fixes.
- Sign off your commits (Developer Certificate of Origin): `git commit -s`. This adds a
  `Signed-off-by:` trailer certifying you have the right to submit the contribution under this
  project's license. See [developercertificate.org](https://developercertificate.org/) for the full
  text.
- Open the PR against `main`. Fill in the PR template.
- Expect review comments; iteration is normal.

## License

Heima is licensed under [GPL-2.0](LICENSE). By contributing, you agree that your contributions will
be licensed under the same terms.
