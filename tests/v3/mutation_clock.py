"""Supplement function mutations with the clock threshold and frozen-result declarations."""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MUTATIONS = (
    (
        "execution_reading_mutable",
        "@dataclass(frozen=True, slots=True)\nclass ExecutionClockReading:",
        "@dataclass(frozen=False, slots=True)\nclass ExecutionClockReading:",
        "test_execution_reading_validation_and_immutability",
    ),
    (
        "gap_mutable",
        "@dataclass(frozen=True, slots=True)\nclass ClockGap:",
        "@dataclass(frozen=False, slots=True)\nclass ClockGap:",
        "test_ca498_backward_without_freeze_has_exact_gap_and_diagnostic",
    ),
    (
        "threshold_plus_nanosecond",
        "_ONE_SECOND_NS = 1_000_000_000",
        "_ONE_SECOND_NS = 1_000_000_001",
        "test_exact_nanosecond_threshold_both_directions",
    ),
    (
        "comparison_mutable",
        "@dataclass(frozen=True, slots=True)\nclass ClockComparison:",
        "@dataclass(frozen=False, slots=True)\nclass ClockComparison:",
        "test_exact_nanosecond_threshold_both_directions",
    ),
    (
        "cycle_tick_mutable",
        "@dataclass(frozen=True, slots=True)\nclass CycleTick:",
        "@dataclass(frozen=False, slots=True)\nclass CycleTick:",
        "test_cycle_floor_before_equal_after",
    ),
)


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="heima-clock-mutations-") as directory:
        work = Path(directory)
        for name in ("custom_components", "tests"):
            shutil.copytree(root / name, work / name, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copyfile(root / "pytest-v3.ini", work / "pytest-v3.ini")
        source = work / "custom_components/heima/v3/runtime/clock.py"
        original = source.read_text()
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-c",
            "pytest-v3.ini",
            "tests/v3/runtime/test_cycle_clock.py",
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
                "Clock mutation baseline failed:\n" + baseline.stdout + baseline.stderr
            )
        for name, old, new, expected_test in MUTATIONS:
            if original.count(old) != 1:
                raise SystemExit("Clock mutation target changed: " + name)
            source.write_text(original.replace(old, new, 1))
            result = subprocess.run(
                command, cwd=work, env=environment, capture_output=True, text=True
            )
            if result.returncode != 1 or expected_test not in result.stdout:
                raise SystemExit(
                    "Clock mutation not killed as expected: "
                    + name
                    + "\n"
                    + result.stdout
                    + result.stderr
                )
            print(name + ": killed by " + expected_test)
        source.write_text(original)


if __name__ == "__main__":
    main()
