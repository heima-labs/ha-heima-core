"""Supplement timing-clock mutations with frozen observation/failure records."""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MUTATIONS = (
    ("timing_clock.py", "ClockSample", "test_exact_adapter_capture_and_immutable_sample"),
    (
        "timing_clock.py",
        "ClockRearmFault",
        "test_rearm_failure_keeps_comparison_and_gap_observable",
    ),
    (
        "timing.py",
        "WallClockRearmFailure",
        "test_scheduler_returns_immutable_per_job_failure_detail",
    ),
)


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="heima-timing-clock-mutations-") as directory:
        work = Path(directory)
        for name in ("custom_components", "tests"):
            shutil.copytree(root / name, work / name, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy2(root / "pytest-v3.ini", work / "pytest-v3.ini")
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-c",
            "pytest-v3.ini",
            "tests/v3/runtime/test_timing_clock.py",
            "tests/v3/adapters/test_clock_source.py",
            "--hypothesis-seed=3145",
            "-x",
            "-q",
        ]
        environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
        baseline = subprocess.run(
            command, cwd=work, env=environment, capture_output=True, text=True
        )
        if baseline.returncode != 0:
            raise SystemExit("Timing clock baseline failed:\n" + baseline.stdout + baseline.stderr)
        for filename, name, expected_test in MUTATIONS:
            source = work / "custom_components/heima/v3/runtime" / filename
            original = source.read_text()
            old = "@dataclass(frozen=True, slots=True)\nclass " + name + ":"
            new = "@dataclass(frozen=False, slots=True)\nclass " + name + ":"
            if original.count(old) != 1:
                raise SystemExit("Mutation target changed: " + name)
            source.write_text(original.replace(old, new, 1))
            result = subprocess.run(
                command, cwd=work, env=environment, capture_output=True, text=True
            )
            source.write_text(original)
            if result.returncode != 1 or expected_test not in result.stdout:
                raise SystemExit(
                    "Mutation not killed: " + name + "\n" + result.stdout + result.stderr
                )
            print(name + ": killed by " + expected_test)


if __name__ == "__main__":
    main()
