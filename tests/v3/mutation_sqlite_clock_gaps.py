"""Semantic SQL replay and immutable-operation mutations with real DB regressions."""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MUTATIONS = (
    (
        "mutable_operation",
        "@dataclass(frozen=True, slots=True)",
        "@dataclass(frozen=False, slots=True)",
        "test_staged_operation_is_immutable",
    ),
    (
        "dynamic_operation_shape",
        "@dataclass(frozen=True, slots=True)",
        "@dataclass(frozen=True, slots=False)",
        "test_staged_operation_is_immutable",
    ),
    (
        "overwrite_conflicting_identity",
        "ON CONFLICT(gap_id, boundary) DO NOTHING",
        "ON CONFLICT(gap_id, boundary) DO UPDATE SET when_utc=excluded.when_utc, includes_boundary=excluded.includes_boundary",
        "test_identity_replay_decision_table_preserves_original_boundary",
    ),
    (
        "ignore_inclusion_on_replay",
        "if stored != expected:",
        "if stored[:3] != expected[:3]:",
        "test_identity_replay_decision_table_preserves_original_boundary",
    ),
    (
        "ignore_payload_on_replay",
        "if stored != expected:",
        "if stored[:2] != expected[:2]:",
        "test_identity_replay_decision_table_preserves_original_boundary",
    ),
)


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="heima-clock-sql-mutations-") as directory:
        work = Path(directory)
        for name in ("custom_components", "tests"):
            shutil.copytree(root / name, work / name, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copyfile(root / "pytest-v3.ini", work / "pytest-v3.ini")
        source = work / "custom_components/heima/v3/storage/sqlite_clock_gaps.py"
        original = source.read_text()
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "-c",
            "pytest-v3.ini",
            "tests/v3/storage/test_sqlite_clock_gaps.py",
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
            raise SystemExit(
                "Clock SQL mutation baseline failed:\n" + baseline.stdout + baseline.stderr
            )
        for name, target, replacement, expected in MUTATIONS:
            if original.count(target) != 1:
                raise SystemExit("Clock SQL mutation target changed: " + name)
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
                    "Clock SQL mutation not killed as expected: "
                    + name
                    + "\n"
                    + result.stdout
                    + result.stderr
                )
            print(name + ": killed by " + expected)
        source.write_text(original)


if __name__ == "__main__":
    main()
