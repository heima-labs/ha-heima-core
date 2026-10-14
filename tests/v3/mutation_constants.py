"""Supplement mutmut's function scope with module/decorator mutations."""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MUTATIONS = (
    (
        "integer_cap",
        "MAX_SAFE_INTEGER = 2**53 - 1",
        "MAX_SAFE_INTEGER = 2**53",
        "test_invalid_value_and_evidence",
    ),
    (
        "depth_cap",
        "MAX_COLLECTION_DEPTH = 2",
        "MAX_COLLECTION_DEPTH = 3",
        "test_invalid_value_and_evidence",
    ),
    (
        "size_cap",
        "MAX_PAYLOAD_BYTES = 8 * 1024",
        "MAX_PAYLOAD_BYTES = 8 * 1024 + 1",
        "test_ascii_size_boundary",
    ),
    (
        "result_frozen",
        "@dataclass(frozen=True, slots=True)\nclass EvidencePreparation",
        "@dataclass(frozen=False, slots=True)\nclass EvidencePreparation",
        "test_diagnostic_and_evidence_result_immutable",
    ),
    (
        "diagnostic_frozen",
        "@dataclass(frozen=True, slots=True)\nclass PayloadDiagnostic",
        "@dataclass(frozen=False, slots=True)\nclass PayloadDiagnostic",
        "test_diagnostic_and_evidence_result_immutable",
    ),
    (
        "payload_frozen",
        "@dataclass(frozen=True, slots=True, eq=False)",
        "@dataclass(frozen=False, slots=True, eq=False)",
        "test_nested_immutability_and_detachment",
    ),
)


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="heima-payload-mutations-") as directory:
        work = Path(directory)
        for name in ("custom_components", "tests"):
            shutil.copytree(root / name, work / name, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copyfile(root / "pytest-v3.ini", work / "pytest-v3.ini")
        source = work / "custom_components/heima/v3/contracts/payloads.py"
        original = source.read_text()
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-c",
            "pytest-v3.ini",
            "tests/v3/contracts",
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


if __name__ == "__main__":
    main()
