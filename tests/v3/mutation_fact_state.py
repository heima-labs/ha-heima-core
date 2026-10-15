"""State projection decorators and semantic mutation supplements."""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MUTATIONS = (
    (
        "FactIdentityKey_frozen",
        "@dataclass(frozen=True, slots=True, init=False)\nclass FactIdentityKey:",
        "@dataclass(frozen=False, slots=True, init=False)\nclass FactIdentityKey:",
        "test_exact_envelopes_and_source_projection",
    ),
    (
        "FactIdentityKey_slots",
        "@dataclass(frozen=True, slots=True, init=False)\nclass FactIdentityKey:",
        "@dataclass(frozen=True, slots=False, init=False)\nclass FactIdentityKey:",
        "test_exact_envelopes_and_source_projection",
    ),
    (
        "FactChangeFingerprint_frozen",
        "@dataclass(frozen=True, slots=True, init=False, eq=False)\nclass FactChangeFingerprint:",
        "@dataclass(frozen=False, slots=True, init=False, eq=False)\nclass FactChangeFingerprint:",
        "test_exact_envelopes_and_source_projection",
    ),
    (
        "FactChangeFingerprint_slots",
        "@dataclass(frozen=True, slots=True, init=False, eq=False)\nclass FactChangeFingerprint:",
        "@dataclass(frozen=True, slots=False, init=False, eq=False)\nclass FactChangeFingerprint:",
        "test_exact_envelopes_and_source_projection",
    ),
    (
        "eager_unavailable_projection",
        "_value_projection(fact.value) if fact.how.available else None",
        "_value_projection(fact.value)",
        "test_unavailable_value_is_not_inspected",
    ),
    (
        "native_bool_numeric_equality",
        "return canonical_json_bytes(self) == canonical_json_bytes(other)",
        "return (self.available, self.confidence, self.value, self.source) == (other.available, other.confidence, other.value, other.source)",
        "test_canonical_value_equivalence",
    ),
)


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="heima-fact-state-mutations-") as directory:
        work = Path(directory)
        for name in ("custom_components", "tests"):
            shutil.copytree(root / name, work / name, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copyfile(root / "pytest-v3.ini", work / "pytest-v3.ini")
        source = work / "custom_components/heima/v3/contracts/fact_state.py"
        original = source.read_text()
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "-c",
            "pytest-v3.ini",
            "tests/v3/contracts/test_fact_state.py",
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
            raise SystemExit("Fact mutation baseline failed:\n" + baseline.stdout + baseline.stderr)
        for name, target, replacement, expected in MUTATIONS:
            if original.count(target) != 1:
                raise SystemExit("Fact mutation target changed: " + name)
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
                    "Fact mutation not killed as expected: "
                    + name
                    + "\n"
                    + result.stdout
                    + result.stderr
                )
            print(name + ": killed by " + expected)
        source.write_text(original)


if __name__ == "__main__":
    main()
