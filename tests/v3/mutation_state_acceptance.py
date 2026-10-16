"""Live state comparison, cycle lifecycle and order mutation supplements."""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MUTATIONS = (
    (
        "AppendOrder_frozen",
        "@dataclass(frozen=True, slots=True)\nclass AppendOrder:",
        "@dataclass(frozen=False, slots=True)\nclass AppendOrder:",
        "test_record_validation_immutability_and_envelope_separation",
    ),
    (
        "AppendOrder_slots",
        "@dataclass(frozen=True, slots=True)\nclass AppendOrder:",
        "@dataclass(frozen=True, slots=False)\nclass AppendOrder:",
        "test_record_validation_immutability_and_envelope_separation",
    ),
    (
        "AcceptedStateTransition_frozen",
        "@dataclass(frozen=True, slots=True)\nclass AcceptedStateTransition:",
        "@dataclass(frozen=False, slots=True)\nclass AcceptedStateTransition:",
        "test_record_validation_immutability_and_envelope_separation",
    ),
    (
        "AcceptedStateTransition_slots",
        "@dataclass(frozen=True, slots=True)\nclass AcceptedStateTransition:",
        "@dataclass(frozen=True, slots=False)\nclass AcceptedStateTransition:",
        "test_record_validation_immutability_and_envelope_separation",
    ),
    (
        "StateCycleContext_frozen",
        "@dataclass(frozen=True, slots=True, init=False)\nclass StateCycleContext:",
        "@dataclass(frozen=False, slots=True, init=False)\nclass StateCycleContext:",
        "test_record_validation_immutability_and_envelope_separation",
    ),
    (
        "StateCycleContext_slots",
        "@dataclass(frozen=True, slots=True, init=False)\nclass StateCycleContext:",
        "@dataclass(frozen=True, slots=False, init=False)\nclass StateCycleContext:",
        "test_record_validation_immutability_and_envelope_separation",
    ),
    (
        "none_evidence_is_omitted",
        "_OMITTED = object()",
        "_OMITTED = None",
        "test_diagnostics_are_consumed_for_changed_and_unchanged_candidates",
    ),
    (
        "forget_live_current",
        "self._current[key] = _CurrentState(transition, fingerprint)",
        "pass",
        "test_on_off_on_keeps_every_transition_at_one_instant_and_last_current",
    ),
    (
        "compare_value_only",
        "if previous.fingerprint == fingerprint:",
        "if previous.transition.fact.value == built.fact.value:",
        "test_state_change_decision_table",
    ),
    (
        "close_keeps_cycle_open",
        "self._cycle = None",
        "self._cycle = cycle",
        "test_time_and_correlation_only_preserve_original_current_without_new_order",
    ),
    (
        "leave_mutation_locked",
        "finally:\n            self._busy = False",
        "finally:\n            pass",
        "test_builder_failure_leaves_index_and_order_unchanged_and_unlocks_coordinator",
    ),
    (
        "do_not_reset_cycle_order",
        "self._last_when = when\n            self._ordinal = 0",
        "self._last_when = when",
        "test_time_and_correlation_only_preserve_original_current_without_new_order",
    ),
    (
        "omit_post_diagnostic_generation_check",
        "self._require_current(cycle)\n            previous",
        "previous",
        "test_generation_change_inside_diagnostic_sink_prevents_live_mutation",
    ),
    (
        "omit_expected_port_generation",
        "producer.require_generation(cycle.generation)",
        "pass",
        "test_port_from_another_snapshot_is_rejected_even_if_its_own_reader_reports_active",
    ),
)


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="heima-live-state-acceptance-mutations-") as directory:
        work = Path(directory)
        for name in ("custom_components", "tests"):
            shutil.copytree(root / name, work / name, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copyfile(root / "pytest-v3.ini", work / "pytest-v3.ini")
        source = work / "custom_components/heima/v3/runtime/state_acceptance.py"
        original = source.read_text()
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "-c",
            "pytest-v3.ini",
            "tests/v3/runtime/test_state_acceptance.py",
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
