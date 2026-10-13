# V3 Python and test environment

Python 3.14.5 was approved on 2026-10-13, aligned with Home Assistant's current
minimum of Python 3.14.2 ([official setup guide](https://developers.home-assistant.io/docs/development_environment/)).
The environment is `.venv-v3`, created from the workspace-local CPython 3.14.5
arm64 runtime in `.python-v3/cpython-3.14.5-macos-aarch64-none`.
V3 tools use dedicated config files; inherited V2 configuration is unchanged.

## Reproduce the environment

```bash
# If a suitable native interpreter is already installed, use its explicit path.
# On this M1 workspace, the local managed runtime is used:
.python-v3/cpython-3.14.5-macos-aarch64-none/bin/python3.14 -m venv .venv-v3
.venv-v3/bin/python -c 'import platform, sys; print(sys.version); assert platform.machine() == "arm64"'
.venv-v3/bin/python -m pip install --require-hashes --only-binary=:all: -r requirements-v3-dev.txt
.venv-v3/bin/python -m pip check
```

Verify that the selected interpreter is Python 3.14.5. The lock was resolved and
verified on macOS arm64 (Apple M1) for that interpreter. It pins direct/transitive tool
versions and artifact hashes; it does not freeze the OS or an HA deployment.
Validate the lock on the eventual CI/lab platform before claiming support there.

The input `requirements-v3-dev.in` records the tooling dependencies. The pinned
`requirements-v3-dev.txt` is the installation input. To deliberately refresh it:

```bash
.venv-v3/bin/pip-compile --generate-hashes --allow-unsafe --strip-extras --output-file=requirements-v3-dev.txt requirements-v3-dev.in
```

`--allow-unsafe` includes pip and setuptools in the hashed lock; it is pip-tools'
option name, not permission to bypass hash checking. pip-tools is a development
resolver, not a V3 runtime dependency. The lock contains no HA runtime/harness;
that release target belongs to the adapter phase.

## Commands once V3 modules/tests exist

```bash
.venv-v3/bin/python -m pytest -c pytest-v3.ini tests/v3 --cov=custom_components.heima.v3 --cov-branch --cov-report=term-missing
.venv-v3/bin/ruff check --config ruff-v3.toml custom_components/heima/v3 tests/v3
.venv-v3/bin/ruff format --check --config ruff-v3.toml custom_components/heima/v3 tests/v3
.venv-v3/bin/python -m mypy --config-file mypy-v3.ini custom_components/heima/v3
```

The V3 package/tests have not been created yet. Import isolation and mutation
paths will be configured in the next agreed step; those suite commands do not
yet constitute an executable V3 test suite.

## Evidence for the five methods

- Decision Tables and Boundary Value Analysis: parametrized pytest cases with
  decision-row/boundary identities and independently derived expected results.
- MC/DC: explicit test pairs for each atomic condition's independent effect in
  a compound decision. coverage.py line/branch data does not certify MC/DC.
- Property-Based Testing: Hypothesis properties, reproducible failing examples,
  explicit seeds when replaying a run, and shrinking.
- Mutation Testing: mutmut scoped to changed V3 functions, with surviving and
  equivalent mutants reviewed. mutmut 3 mutates functions; executable logic
  outside its scope needs supplementary targeted mutation evidence.

Ruff provides lint/format checks and mypy provides type checks. No coverage or
mutation percentage threshold has been chosen.

## Workspace-local Python installation

The system's `/usr/local/bin/python3.14` is Intel-only; the native Homebrew
Python in `/opt/homebrew` is 3.13. The old native Homebrew cannot recognize the
current macOS release. Instead of changing system packages, this task used uv
0.13.0 in a temporary native bootstrap environment to install an arm64 CPython
3.14.5 distribution locally. uv uses Astral's python-build-standalone builds
([official guide](https://docs.astral.sh/uv/guides/install-python/)).

With a native uv available, the equivalent local installation is:

```bash
UV_PYTHON_INSTALL_DIR="$PWD/.python-v3" UV_PYTHON_BIN_DIR="$PWD/.python-v3/bin" uv python install cpython-3.14.5-macos-aarch64-none
```

The runtime and venv are ignored local artifacts. No global Homebrew update,
shell/PATH modification or Rust toolchain installation is needed. The initial
Intel venv was retired to `/private/tmp/heima-v3-python314/venv-intel-retired`
and is not the V3 development environment. The final native environment uses
mutmut 3.8.0 and LibCST 1.9.0 with arm64 wheels; the earlier Intel-only downgrade
workaround is not in the final requirements.

## Verification

The results below concern temporary tool probes outside the repository. They do
not implement or test Heima V3 behavior, and no HA/V2 runtime is initialized.

Verified on 2026-10-13:

| Check | Result |
|---|---|
| Interpreter version/architecture and executable file | Python 3.14.5; `platform.machine() == "arm64"`; Mach-O arm64 |
| Hashed wheel-only dependency installation | Passed; no Rust build |
| `pip check` | No broken requirements |
| pytest parametrized decisions/boundaries, Hypothesis (seed 3145), asyncio | 9 tests passed |
| Ruff lint and format check using V3 config | Passed |
| mypy using Python 3.14 V3 config | Passed on the temporary probe |
| mutmut baseline, forced-failure check and mutations | 3/3 killed; 0 survived; no timeout |

Pinned top-level versions: pytest 9.1.1, pytest-asyncio 1.4.0, pytest-cov 7.1.0,
Hypothesis 6.169.0, mutmut 3.8.0, Ruff 0.17.0, mypy 2.4.0 and pip-tools 7.6.2.
LibCST 1.9.0 is a pinned mutation-tool dependency. SQLite linked to this local
interpreter is 3.53.1; eventual HA storage/crash tests must verify their own runtime.
These probes establish local tool usability, not a mutation score for V3.
