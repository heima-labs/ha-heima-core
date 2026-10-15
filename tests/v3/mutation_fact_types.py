"""Fact claim record decorator mutations."""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MUTATIONS = (
    (
        "FactTypeClaim_frozen",
        "@dataclass(frozen=True, slots=True)\nclass FactTypeClaim:",
        "@dataclass(frozen=False, slots=True)\nclass FactTypeClaim:",
        "test_claim_envelope_and_immutability",
    ),
    (
        "FactTypeClaim_slots",
        "@dataclass(frozen=True, slots=True)\nclass FactTypeClaim:",
        "@dataclass(frozen=True, slots=False)\nclass FactTypeClaim:",
        "test_claim_envelope_and_immutability",
    ),
    (
        "visited_state_lost",
        "visited.add(state)",
        "visited.add(None)",
        "test_wildcard_search_stays_within_finite_product",
    ),
    (
        "one_exhausted_input_not_stopped",
        "if a is None or b is None:",
        "if a is None and b is None:",
        "test_wildcard_search_stays_within_finite_product",
    ),
    (
        "epsilon_on_literal",
        'if b == "*":',
        'if b != "*":',
        "test_wildcard_search_stays_within_finite_product",
    ),
)


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="heima-fact-claims-mutations-") as directory:
        work = Path(directory)
        for name in ("custom_components", "tests"):
            shutil.copytree(root / name, work / name, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copyfile(root / "pytest-v3.ini", work / "pytest-v3.ini")
        source = work / "custom_components/heima/v3/contracts/fact_types.py"
        original = source.read_text()
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "-c",
            "pytest-v3.ini",
            "tests/v3/contracts/test_fact_types.py",
            "--hypothesis-seed=3145",
            "-x",
            "-q",
        ]
        environment = {
            **os.environ,
            "PYTHONDONTWRITEBYTECODE": "1",
            "HYPOTHESIS_STORAGE_DIRECTORY": str(work / "hypothesis"),
        }
        baseline = subprocess.run(
            command, cwd=work, env=environment, capture_output=True, text=True
        )
        if baseline.returncode != 0:
            raise SystemExit("Fact mutation baseline failed:\n" + baseline.stdout + baseline.stderr)
        for name, target, replacement, expected in MUTATIONS:
            if original.count(target) != 1:
                raise SystemExit("Fact mutation target changed: " + name)
            source.write_text(original.replace(target, replacement, 1))
            result = subprocess.run(
                [*command, "-k", expected],
                cwd=work,
                env=environment,
                capture_output=True,
                text=True,
            )
            if result.returncode != 1 or expected not in result.stdout:
                raise SystemExit(
                    "Fact mutation not killed as expected: "
                    + name
                    + "\n"
                    + result.stdout
                    + result.stderr
                )
            print(name + ": killed by " + expected)
        source.write_text(original)


if __name__ == "__main__":
    main()
