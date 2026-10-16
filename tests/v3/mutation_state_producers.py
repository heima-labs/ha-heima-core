"""Fixed-source producer port invariants and immutable records."""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MUTATIONS = (
    (
        "FixedStateProducerRegistration_frozen",
        "@dataclass(frozen=True, slots=True)\nclass FixedStateProducerRegistration:",
        "@dataclass(frozen=False, slots=True)\nclass FixedStateProducerRegistration:",
        "test_records_and_map_are_immutable_and_snapshot_inputs_owned",
    ),
    (
        "FixedStateProducerRegistration_slots",
        "@dataclass(frozen=True, slots=True)\nclass FixedStateProducerRegistration:",
        "@dataclass(frozen=True, slots=False)\nclass FixedStateProducerRegistration:",
        "test_records_and_map_are_immutable_and_snapshot_inputs_owned",
    ),
    (
        "PreparedStateProducerGeneration_frozen",
        "@dataclass(frozen=True, slots=True, init=False)\nclass PreparedStateProducerGeneration:",
        "@dataclass(frozen=False, slots=True, init=False)\nclass PreparedStateProducerGeneration:",
        "test_records_and_map_are_immutable_and_snapshot_inputs_owned",
    ),
    (
        "PreparedStateProducerGeneration_slots",
        "@dataclass(frozen=True, slots=True, init=False)\nclass PreparedStateProducerGeneration:",
        "@dataclass(frozen=True, slots=False, init=False)\nclass PreparedStateProducerGeneration:",
        "test_records_and_map_are_immutable_and_snapshot_inputs_owned",
    ),
    (
        "FixedSourceStateProducer_frozen",
        "@dataclass(frozen=True, slots=True, init=False)\nclass FixedSourceStateProducer:",
        "@dataclass(frozen=False, slots=True, init=False)\nclass FixedSourceStateProducer:",
        "test_records_and_map_are_immutable_and_snapshot_inputs_owned",
    ),
    (
        "FixedSourceStateProducer_slots",
        "@dataclass(frozen=True, slots=True, init=False)\nclass FixedSourceStateProducer:",
        "@dataclass(frozen=True, slots=False, init=False)\nclass FixedSourceStateProducer:",
        "test_records_and_map_are_immutable_and_snapshot_inputs_owned",
    ),
    (
        "omit_before_fence",
        "self._require_active()\n        registration",
        "registration",
        "test_inactive_port_rejects_before_inspecting_payload",
    ),
    (
        "omit_after_fence",
        "self._require_active()\n        return result",
        "return result",
        "test_generation_change_during_payload_read_rejects_result",
    ),
    (
        "compare_generation_values",
        "if self._read_active() is not self._generation:",
        "if self._read_active() != self._generation:",
        "test_active_generation_decision_table",
    ),
    (
        "explicit_none_equals_omitted",
        "_OMITTED = object()",
        "_OMITTED = None",
        "test_hard_value_failure_and_soft_evidence_diagnostic_are_preserved",
    ),
    (
        "mutable_registration_map",
        "MappingProxyType(producers)",
        "dict(producers)",
        "test_records_and_map_are_immutable_and_snapshot_inputs_owned",
    ),
    (
        "lost_evidence_diagnostic",
        "return result",
        "return FactBuildResult(result.fact, ())",
        "test_hard_value_failure_and_soft_evidence_diagnostic_are_preserved",
    ),
    (
        "omit_explicit_guard_installed_check",
        "self._require_active()\n\n    def build",
        "pass\n\n    def build",
        "test_explicit_cycle_generation_guard_also_requires_installed_snapshot",
    ),
)


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="heima-state-producer-port-mutations-") as directory:
        work = Path(directory)
        for name in ("custom_components", "tests"):
            shutil.copytree(root / name, work / name, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copyfile(root / "pytest-v3.ini", work / "pytest-v3.ini")
        source = work / "custom_components/heima/v3/runtime/state_producers.py"
        original = source.read_text()
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "-c",
            "pytest-v3.ini",
            "tests/v3/runtime/test_state_producers.py",
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
