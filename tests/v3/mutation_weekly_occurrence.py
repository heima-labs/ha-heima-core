"""Supplement weekly mutations with immutable occurrence and requested-date semantics."""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MUTATIONS = (
    (
        "occurrence_mutable",
        "@dataclass(frozen=True, slots=True)\nclass WeeklyOccurrence:",
        "@dataclass(frozen=False, slots=True)\nclass WeeklyOccurrence:",
        "test_apia_retains_requested_date_instead_of_shifted_start_date",
    ),
    (
        "requested_date_replaced_with_start_date",
        "return WeeklyOccurrence(day, format_instant(due))",
        "return WeeklyOccurrence(due.astimezone(time_zone).date(), format_instant(due))",
        "test_apia_retains_requested_date_instead_of_shifted_start_date",
    ),
)


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="heima-weekly-occurrence-mutations-") as directory:
        work = Path(directory)
        for name in ("custom_components", "tests"):
            shutil.copytree(root / name, work / name, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copyfile(root / "pytest-v3.ini", work / "pytest-v3.ini")
        source = work / "custom_components/heima/v3/runtime/recurrence.py"
        original = source.read_text()
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-c",
            "pytest-v3.ini",
            "tests/v3/runtime/test_weekly_planning.py",
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
                "Weekly occurrence mutation baseline failed:\n" + baseline.stdout + baseline.stderr
            )
        for name, old, new, expected_test in MUTATIONS:
            if original.count(old) != 1:
                raise SystemExit("Weekly occurrence mutation target changed: " + name)
            source.write_text(original.replace(old, new, 1))
            result = subprocess.run(
                command, cwd=work, env=environment, capture_output=True, text=True
            )
            if result.returncode != 1 or expected_test not in result.stdout:
                raise SystemExit(
                    "Weekly occurrence mutation not killed as expected: "
                    + name
                    + "\n"
                    + result.stdout
                    + result.stderr
                )
            print(name + ": killed by " + expected_test)
        source.write_text(original)


if __name__ == "__main__":
    main()
