"""Supplement mutmut property-scope exclusions with discrete interval boundary mutations."""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MUTATIONS = (
    (
        "history_interval_mutable",
        "@dataclass(frozen=True, slots=True)\nclass HistoryInterval:",
        "@dataclass(frozen=False, slots=True)\nclass HistoryInterval:",
        "test_immutability_and_independent_intersection_validation",
    ),
    (
        "empty_threshold_inclusive",
        "return microseconds < excluded",
        "return microseconds <= excluded",
        "test_touching_boundary_requires_both_inclusions",
    ),
    (
        "endpoint_exclusions_subtracted",
        "int(not self.include_start) + int(not self.include_end)",
        "int(not self.include_start) - int(not self.include_end)",
        "test_touching_boundary_requires_both_inclusions",
    ),
    (
        "start_exclusion_ignored",
        "int(not self.include_start) + int(not self.include_end)",
        "0 + int(not self.include_end)",
        "test_touching_boundary_requires_both_inclusions",
    ),
    (
        "end_exclusion_ignored",
        "int(not self.include_start) + int(not self.include_end)",
        "int(not self.include_start) + 0",
        "test_touching_boundary_requires_both_inclusions",
    ),
)


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="heima-history-interval-mutations-") as directory:
        work = Path(directory)
        for name in ("custom_components", "tests"):
            shutil.copytree(root / name, work / name, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copyfile(root / "pytest-v3.ini", work / "pytest-v3.ini")
        source = work / "custom_components/heima/v3/contracts/history_intervals.py"
        original = source.read_text()
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-c",
            "pytest-v3.ini",
            "tests/v3/contracts/test_history_intervals.py",
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
                "History interval mutation baseline failed:\n" + baseline.stdout + baseline.stderr
            )
        for name, old, new, expected_test in MUTATIONS:
            if original.count(old) != 1:
                raise SystemExit("History interval mutation target changed: " + name)
            source.write_text(original.replace(old, new, 1))
            result = subprocess.run(
                command, cwd=work, env=environment, capture_output=True, text=True
            )
            if result.returncode != 1 or expected_test not in result.stdout:
                raise SystemExit(
                    "History interval mutation not killed as expected: "
                    + name
                    + "\n"
                    + result.stdout
                    + result.stderr
                )
            print(name + ": killed by " + expected_test)
        source.write_text(original)


if __name__ == "__main__":
    main()
