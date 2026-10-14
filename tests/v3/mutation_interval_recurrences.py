"""Supplement function mutations with immutable interval lifecycle diagnostics."""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MUTATIONS = (
    (
        "callback_fault_mutable",
        "@dataclass(frozen=True, slots=True)\nclass JobCallbackFault:",
        "@dataclass(frozen=False, slots=True)\nclass JobCallbackFault:",
        "test_callback_failure_is_diagnosed_and_recurring_safety_net_survives",
    ),
    (
        "rearm_fault_mutable",
        "@dataclass(frozen=True, slots=True)\nclass IntervalRearmFault:",
        "@dataclass(frozen=False, slots=True)\nclass IntervalRearmFault:",
        "test_rearm_failure_is_reported_and_definition_is_retained",
    ),
    (
        "rejection_mutable",
        "@dataclass(frozen=True, slots=True)\nclass IntervalDeadlineRejected:",
        "@dataclass(frozen=False, slots=True)\nclass IntervalDeadlineRejected:",
        "test_overflow_admission_reports_once_without_changing_active_rule",
    ),
)


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="heima-interval-mutations-") as directory:
        work = Path(directory)
        for name in ("custom_components", "tests"):
            shutil.copytree(root / name, work / name, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copyfile(root / "pytest-v3.ini", work / "pytest-v3.ini")
        source = work / "custom_components/heima/v3/runtime/interval_recurrences.py"
        original = source.read_text()
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-c",
            "pytest-v3.ini",
            "tests/v3/runtime/test_interval_recurrences.py",
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
                "Interval lifecycle mutation baseline failed:\n" + baseline.stdout + baseline.stderr
            )
        for name, old, new, expected_test in MUTATIONS:
            if original.count(old) != 1:
                raise SystemExit("Interval lifecycle mutation target changed: " + name)
            source.write_text(original.replace(old, new, 1))
            result = subprocess.run(
                command, cwd=work, env=environment, capture_output=True, text=True
            )
            if result.returncode != 1 or expected_test not in result.stdout:
                raise SystemExit(
                    "Interval lifecycle mutation not killed as expected: "
                    + name
                    + "\n"
                    + result.stdout
                    + result.stderr
                )
            print(name + ": killed by " + expected_test)
        source.write_text(original)


if __name__ == "__main__":
    main()
