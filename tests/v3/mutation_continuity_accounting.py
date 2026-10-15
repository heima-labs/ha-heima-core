"""Supplement mutmut with immutable continuity accounting declarations."""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="heima-accounting-mutations-") as directory:
        work = Path(directory)
        for name in ("custom_components", "tests"):
            shutil.copytree(root / name, work / name, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copyfile(root / "pytest-v3.ini", work / "pytest-v3.ini")
        source = work / "custom_components/heima/v3/storage/continuity_accounting.py"
        original = source.read_text()
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "-c",
            "pytest-v3.ini",
            "tests/v3/storage/test_continuity_accounting.py",
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
            raise SystemExit("Accounting baseline failed:\n" + baseline.stdout + baseline.stderr)
        for name in ("ContinuityAccountingBarrier", "DurabilityRange"):
            target = "@dataclass(frozen=True, slots=True)\nclass " + name + ":"
            if original.count(target) != 1:
                raise SystemExit("Accounting mutation target changed: " + name)
            source.write_text(
                original.replace(target, target.replace("frozen=True", "frozen=False"), 1)
            )
            mutated = subprocess.run(
                command, cwd=work, env=environment, capture_output=True, text=True
            )
            expected = "test_snapshot_types_are_immutable_and_revalidated"
            if mutated.returncode != 1 or expected not in mutated.stdout:
                raise SystemExit(
                    "Accounting mutation not killed: "
                    + name
                    + "\n"
                    + mutated.stdout
                    + mutated.stderr
                )
            print(name + ": mutable mutation killed by " + expected)
        source.write_text(original)


if __name__ == "__main__":
    main()
