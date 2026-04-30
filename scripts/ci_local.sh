#!/usr/bin/env bash
# Run full CI locally — mirrors .github/workflows/ci.yml exactly.
# Must be run from the repo root.
set -e

echo "==> Installing dependencies"
pip install -r requirements-dev.txt
pip install pytest-cov ruff mypy

echo "==> Tests + Coverage"
pytest -q --cov=custom_components/heima --cov-report=term-missing --cov-fail-under=70

echo "==> Lint (ruff check)"
ruff check custom_components/heima tests

echo "==> Format check (ruff format)"
ruff format --check custom_components/heima tests

echo "==> Type check (mypy — informativo)"
mypy custom_components/heima --ignore-missing-imports --no-error-summary || true

echo "==> CI locale completata."
