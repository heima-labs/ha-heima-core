# V3 behavioral tests

Run `.venv-v3/bin/python -m pytest -c pytest-v3.ini tests/v3 --hypothesis-seed=3145`.
Install both runtime and development locks first. Tests import the real packages,
including the mutated copy under mutmut; no HA or V2 parent shim is used.
See `docs/v3/testing/PAYLOAD_CONTRACT.md` for the five-method evidence and the
supplementary module/decorator mutation runner.
