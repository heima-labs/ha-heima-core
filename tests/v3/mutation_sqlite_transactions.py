"""Supplement generic mutations with plausible SQL semantics and early publication."""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MUTATIONS = (
    (
        "publish_before_commit",
        '            self._connection.execute("COMMIT")',
        '            return result\n            self._connection.execute("COMMIT")',
        "test_result_receipt_is_returned_only_after_atomic_commit_visible_to_another_connection",
    ),
    (
        "rollback_instead_of_commit",
        '            self._connection.execute("COMMIT")',
        '            self._connection.execute("ROLLBACK")',
        "test_result_receipt_is_returned_only_after_atomic_commit_visible_to_another_connection",
    ),
    (
        "allow_callback_transaction_control",
        "        return SQLITE_DENY",
        "        return SQLITE_OK",
        "test_accidental_commit_then_begin_cannot_publish_a_partially_committed_batch",
    ),
)


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="heima-sqlite-mutations-") as directory:
        work = Path(directory)
        for name in ("custom_components", "tests"):
            shutil.copytree(root / name, work / name, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copyfile(root / "pytest-v3.ini", work / "pytest-v3.ini")
        source = work / "custom_components/heima/v3/storage/sqlite_transactions.py"
        original = source.read_text()
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "-c",
            "pytest-v3.ini",
            "tests/v3/storage/test_sqlite_transactions.py",
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
                "SQLite mutation baseline failed:\n" + baseline.stdout + baseline.stderr
            )
        for name, target, replacement, expected in MUTATIONS:
            if original.count(target) != 1:
                raise SystemExit("SQLite mutation target changed: " + name)
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
                    "SQLite mutation not killed as expected: "
                    + name
                    + "\n"
                    + result.stdout
                    + result.stderr
                )
            print(name + ": killed by " + expected)
        source.write_text(original)


if __name__ == "__main__":
    main()
