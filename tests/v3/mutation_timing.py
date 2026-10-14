"""Supplement mutmut's function scope with temporal constructor decorator mutations."""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MUTATIONS = tuple(
    (
        name + "_frozen",
        "@dataclass(frozen=True, slots=True)\nclass " + name + ":",
        "@dataclass(frozen=False, slots=True)\nclass " + name + ":",
        test,
    )
    for name, test in [
        ("Window", "test_duration_valid_and_canonical"),
        ("AtJob", "test_job_and_cron_definitions_immutable"),
        ("WeeklyRecurrence", "test_weekly_bounds_valid"),
        ("IntervalRecurrence", "test_weekly_uses_explicit_zone_not_host_zone"),
        ("CronEntry", "test_job_and_cron_definitions_immutable"),
        ("CalendarWindow", "test_calendar_half_open_boundaries_and_summary_preserved"),
    ]
)


# These mutations exercise independent nested-duration admission, not just the
# frozen decorator or Window's own constructor.
_INTERVAL_ADMISSION = '        object.__setattr__(self, "interval", Window(self.interval.seconds))'
MUTATIONS += (
    (
        "interval_missing_admission",
        _INTERVAL_ADMISSION,
        "        pass",
        "test_interval_validates_nested_duration_independently",
    ),
    (
        "interval_constant_duration",
        _INTERVAL_ADMISSION,
        '        object.__setattr__(self, "interval", Window(1))',
        "test_interval_validates_nested_duration_independently",
    ),
    (
        "interval_missing_normalization",
        _INTERVAL_ADMISSION,
        "        Window(self.interval.seconds)",
        "test_interval_normalizes_nested_duration_without_changing_input",
    ),
)


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="heima-timing-mutations-") as directory:
        work = Path(directory)
        for name in ("custom_components", "tests"):
            shutil.copytree(root / name, work / name, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copyfile(root / "pytest-v3.ini", work / "pytest-v3.ini")
        source = work / "custom_components/heima/v3/contracts/timing.py"
        original = source.read_text()
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-c",
            "pytest-v3.ini",
            "tests/v3/contracts/test_timing.py",
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
                "Supplementary mutation baseline failed:\n" + baseline.stdout + baseline.stderr
            )
        for name, old, new, expected_test in MUTATIONS:
            if original.count(old) != 1:
                raise SystemExit("Mutation target changed: " + name)
            source.write_text(original.replace(old, new, 1))
            result = subprocess.run(
                command, cwd=work, env=environment, capture_output=True, text=True
            )
            if result.returncode != 1 or expected_test not in result.stdout:
                raise SystemExit(
                    "Mutation not killed by expected test: "
                    + name
                    + "\n"
                    + result.stdout
                    + result.stderr
                )
            print(name + ": killed by " + expected_test)
        source.write_text(original)
        source = work / "custom_components/heima/v3/contracts/instants.py"
        original = source.read_text()
        source.write_text(original.replace("[0-9]{4}", "2026", 1))
        result = subprocess.run(command, cwd=work, env=environment, capture_output=True, text=True)
        if (
            result.returncode != 1
            or "test_instant_valid_calendar_and_exact_precision" not in result.stdout
        ):
            raise SystemExit("Instant-pattern mutation not killed by expected test")
        print("instant_pattern: killed by test_instant_valid_calendar_and_exact_precision")
        source.write_text(original)


if __name__ == "__main__":
    main()
