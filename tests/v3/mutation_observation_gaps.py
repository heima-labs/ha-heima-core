"""Supplement mutmut's function scope with the immutable gap declaration."""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="heima-gap-clipping-mutation-") as directory:
        work = Path(directory)
        for name in ("custom_components", "tests"):
            shutil.copytree(root / name, work / name, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copyfile(root / "pytest-v3.ini", work / "pytest-v3.ini")
        source = work / "custom_components/heima/v3/contracts/observation_gaps.py"
        original = source.read_text()
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "-c",
            "pytest-v3.ini",
            "tests/v3/contracts/test_observation_gaps.py",
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
            raise SystemExit("Gap mutation baseline failed:\n" + baseline.stdout + baseline.stderr)
        target = "@dataclass(frozen=True, slots=True)"
        if original.count(target) != 1:
            raise SystemExit("Gap decorator mutation target changed")
        source.write_text(original.replace(target, "@dataclass(frozen=False, slots=True)", 1))
        mutated = subprocess.run(command, cwd=work, env=environment, capture_output=True, text=True)
        expected_test = "test_input_shapes_and_immutable_result"
        if mutated.returncode != 1 or expected_test not in mutated.stdout:
            raise SystemExit(
                "Mutable gap mutation not killed as expected:\n" + mutated.stdout + mutated.stderr
            )
        print("gap_mutable: killed by " + expected_test)


if __name__ == "__main__":
    main()
