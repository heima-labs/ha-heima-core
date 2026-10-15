"""Supplement coverage mutations with immutable result and closed reason registry."""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MUTATIONS = (
    (
        "coverage_mutable",
        "@dataclass(frozen=True, slots=True)\nclass ObservationCoverage:",
        "@dataclass(frozen=False, slots=True)\nclass ObservationCoverage:",
        "test_every_declared_reason_has_valid_immutable_result",
    ),
    (
        "declared_reason_missing",
        "_GAP_REASONS = frozenset(get_args(ObservationGapReason.__value__))",
        '_GAP_REASONS = frozenset(get_args(ObservationGapReason.__value__)) - {"process_interruption"}',
        "test_every_declared_reason_has_valid_immutable_result",
    ),
    (
        "undeclared_reason_accepted",
        "_GAP_REASONS = frozenset(get_args(ObservationGapReason.__value__))",
        '_GAP_REASONS = frozenset(get_args(ObservationGapReason.__value__)) | {"made_up"}',
        "test_rejects_invalid_or_contradictory_result",
    ),
)


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="heima-observation-mutations-") as directory:
        work = Path(directory)
        for name in ("custom_components", "tests"):
            shutil.copytree(root / name, work / name, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copyfile(root / "pytest-v3.ini", work / "pytest-v3.ini")
        source = work / "custom_components/heima/v3/contracts/observation.py"
        original = source.read_text()
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-c",
            "pytest-v3.ini",
            "tests/v3/contracts/test_observation.py",
            "--hypothesis-seed=3145",
            "-x",
            "-q",
        ]
        environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
        baseline = subprocess.run(
            command, cwd=work, env=environment, capture_output=True, text=True
        )
        if baseline.returncode != 0:
            raise SystemExit(
                "Observation coverage mutation baseline failed:\n"
                + baseline.stdout
                + baseline.stderr
            )
        for name, old, new, expected_test in MUTATIONS:
            if original.count(old) != 1:
                raise SystemExit("Observation coverage mutation target changed: " + name)
            source.write_text(original.replace(old, new, 1))
            result = subprocess.run(
                command, cwd=work, env=environment, capture_output=True, text=True
            )
            if result.returncode != 1 or expected_test not in result.stdout:
                raise SystemExit(
                    "Observation coverage mutation not killed as expected: "
                    + name
                    + "\n"
                    + result.stdout
                    + result.stderr
                )
            print(name + ": killed by " + expected_test)
        source.write_text(original)


if __name__ == "__main__":
    main()
