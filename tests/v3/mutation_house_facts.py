"""Fact envelopes, omission semantics and canonical equality mutations."""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MUTATIONS = (
    (
        "HouseFact_frozen",
        "@dataclass(frozen=True, slots=True, init=False, eq=False)\nclass HouseFact:",
        "@dataclass(frozen=False, slots=True, init=False, eq=False)\nclass HouseFact:",
        "test_input_graph_is_detached_and_both_payloads_are_deeply_immutable",
    ),
    (
        "HouseFact_slots",
        "@dataclass(frozen=True, slots=True, init=False, eq=False)\nclass HouseFact:",
        "@dataclass(frozen=True, slots=False, init=False, eq=False)\nclass HouseFact:",
        "test_records_and_result_are_slotted_and_result_is_frozen",
    ),
    (
        "Provenance_frozen",
        "@dataclass(frozen=True, slots=True, init=False, eq=False)\nclass Provenance:",
        "@dataclass(frozen=False, slots=True, init=False, eq=False)\nclass Provenance:",
        "test_input_graph_is_detached_and_both_payloads_are_deeply_immutable",
    ),
    (
        "Provenance_slots",
        "@dataclass(frozen=True, slots=True, init=False, eq=False)\nclass Provenance:",
        "@dataclass(frozen=True, slots=False, init=False, eq=False)\nclass Provenance:",
        "test_records_and_result_are_slotted_and_result_is_frozen",
    ),
    (
        "FactBuildResult_frozen",
        "@dataclass(frozen=True, slots=True)\nclass FactBuildResult:",
        "@dataclass(frozen=False, slots=True)\nclass FactBuildResult:",
        "test_records_and_result_are_slotted_and_result_is_frozen",
    ),
    (
        "FactBuildResult_slots",
        "@dataclass(frozen=True, slots=True)\nclass FactBuildResult:",
        "@dataclass(frozen=True, slots=False)\nclass FactBuildResult:",
        "test_records_and_result_are_slotted_and_result_is_frozen",
    ),
    (
        "omitted_equals_explicit_none",
        "_OMITTED = object()",
        "_OMITTED = None",
        "test_missing_evidence_is_clean_while_explicit_none_is_diagnosed",
    ),
    (
        "erase_unavailable_value",
        'object.__setattr__(fact, "value", prepared_value.value)',
        'object.__setattr__(fact, "value", prepared_value.value if available else None)',
        "test_unavailable_value_is_preserved_without_becoming_usable",
    ),
    (
        "lose_evidence_diagnostic",
        "return FactBuildResult(fact, prepared_evidence.diagnostics)",
        "return FactBuildResult(fact, ())",
        "test_evidence_violation_keeps_fact_and_returns_bounded_diagnostic",
    ),
    (
        "native_fact_equality",
        "return house_fact_canonical_bytes(self) == house_fact_canonical_bytes(other)",
        "return (self.fact_type, self.value, self.where, self.when, self.how) == (other.fact_type, other.value, other.where, other.when, other.how)",
        "test_fact_and_provenance_equality_use_canonical_semantics",
    ),
    (
        "native_provenance_equality",
        "return canonical_json_bytes(self) == canonical_json_bytes(other)",
        "return (self.confidence, self.source, self.available, self.evidence) == (other.confidence, other.source, other.available, other.evidence)",
        "test_fact_and_provenance_equality_use_canonical_semantics",
    ),
)


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="heima-house-facts-mutations-") as directory:
        work = Path(directory)
        for name in ("custom_components", "tests"):
            shutil.copytree(root / name, work / name, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copyfile(root / "pytest-v3.ini", work / "pytest-v3.ini")
        source = work / "custom_components/heima/v3/contracts/house_facts.py"
        original = source.read_text()
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "-c",
            "pytest-v3.ini",
            "tests/v3/contracts/test_house_facts.py",
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
