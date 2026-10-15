"""Core reservation and immutable staging-record mutations."""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MUTATIONS = (
    (
        "omit_core_1",
        '    FactTypeClaim("manual_hold.lifecycle", "layer0.divergence_hold", "event"),\n',
        "",
        "test_exact_core_reservations_always_included",
    ),
    (
        "omit_core_2",
        '    FactTypeClaim("actuator.resident_control", "layer0.resident_control_ingress", "event"),\n',
        "",
        "test_exact_core_reservations_always_included",
    ),
    (
        "omit_core_3",
        '    FactTypeClaim("actuator.channel_state.*", "layer0.channel_observation", "state"),\n',
        "",
        "test_exact_core_reservations_always_included",
    ),
    (
        "omit_core_4",
        '    FactTypeClaim("actuator.correction", "layer5.correction_attribution", "event"),\n',
        "",
        "test_exact_core_reservations_always_included",
    ),
    (
        "omit_core_5",
        '    FactTypeClaim("actuator.target_lifecycle", "layer5.target_evidence", "event"),\n',
        "",
        "test_exact_core_reservations_always_included",
    ),
    (
        "omit_core_6",
        '    FactTypeClaim("reaction.decision.*", "layer5.reaction_decision", "state"),\n',
        "",
        "test_exact_core_reservations_always_included",
    ),
    (
        "omit_core_7",
        '    FactTypeClaim("reaction.managed_episode.*", "layer5.managed_episode", "state"),\n',
        "",
        "test_exact_core_reservations_always_included",
    ),
    (
        "omit_core_8",
        '    FactTypeClaim("reaction.follow_up", "layer6.reaction_follow_up", "event"),\n',
        "",
        "test_exact_core_reservations_always_included",
    ),
    (
        "omit_core_9",
        '    FactTypeClaim("automation.availability", "layer6.availability", "event"),\n',
        "",
        "test_exact_core_reservations_always_included",
    ),
    (
        "omit_core_10",
        '    FactTypeClaim("reaction.advisory", "layer6.reaction_advisory", "event"),\n',
        "",
        "test_exact_core_reservations_always_included",
    ),
    (
        "omit_core_11",
        '    FactTypeClaim("recovery.confirmation_request", "layer6.recovery_confirmation", "event"),\n',
        "",
        "test_exact_core_reservations_always_included",
    ),
    (
        "omit_core_12",
        '    FactTypeClaim("reaction.action_notice", "layer6.reaction_action_notice", "event"),\n',
        "",
        "test_exact_core_reservations_always_included",
    ),
    (
        "omit_core_13",
        '    FactTypeClaim("proposal.review_pending", "layer6.proposal_review", "event"),\n',
        "",
        "test_exact_core_reservations_always_included",
    ),
    (
        "omit_core_14",
        '    FactTypeClaim("reaction.consent_request", "layer6.consent_request", "event"),\n',
        "",
        "test_exact_core_reservations_always_included",
    ),
    (
        "omit_core_15",
        '    FactTypeClaim("reaction.advisory_feedback", "layer5.advisory_feedback", "event"),\n',
        "",
        "test_exact_core_reservations_always_included",
    ),
    (
        "StaticStateClaim_frozen",
        "@dataclass(frozen=True, slots=True)\nclass StaticStateClaim:",
        "@dataclass(frozen=False, slots=True)\nclass StaticStateClaim:",
        "test_staging_records_are_immutable_exact_and_slotted",
    ),
    (
        "StaticStateClaim_slots",
        "@dataclass(frozen=True, slots=True)\nclass StaticStateClaim:",
        "@dataclass(frozen=True, slots=False)\nclass StaticStateClaim:",
        "test_staging_records_are_immutable_exact_and_slotted",
    ),
    (
        "FactTypeBinding_frozen",
        "@dataclass(frozen=True, slots=True, init=False)\nclass FactTypeBinding:",
        "@dataclass(frozen=False, slots=True, init=False)\nclass FactTypeBinding:",
        "test_staging_records_are_immutable_exact_and_slotted",
    ),
    (
        "FactTypeBinding_slots",
        "@dataclass(frozen=True, slots=True, init=False)\nclass FactTypeBinding:",
        "@dataclass(frozen=True, slots=False, init=False)\nclass FactTypeBinding:",
        "test_staging_records_are_immutable_exact_and_slotted",
    ),
    (
        "ComposedFactProducers_frozen",
        "@dataclass(frozen=True, slots=True, init=False)\nclass ComposedFactProducers:",
        "@dataclass(frozen=False, slots=True, init=False)\nclass ComposedFactProducers:",
        "test_staging_records_are_immutable_exact_and_slotted",
    ),
    (
        "ComposedFactProducers_slots",
        "@dataclass(frozen=True, slots=True, init=False)\nclass ComposedFactProducers:",
        "@dataclass(frozen=True, slots=False, init=False)\nclass ComposedFactProducers:",
        "test_staging_records_are_immutable_exact_and_slotted",
    ),
    (
        "wrong_core_owner",
        '    FactTypeClaim("manual_hold.lifecycle", "layer0.divergence_hold", "event"),',
        '    FactTypeClaim("manual_hold.lifecycle", "layer0.other", "event"),',
        "test_exact_core_reservations_always_included",
    ),
    (
        "wrong_core_kind",
        '    FactTypeClaim("manual_hold.lifecycle", "layer0.divergence_hold", "event"),',
        '    FactTypeClaim("manual_hold.lifecycle", "layer0.divergence_hold", "state"),',
        "test_exact_core_reservations_always_included",
    ),
)


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="heima-producer-staging-mutations-") as directory:
        work = Path(directory)
        for name in ("custom_components", "tests"):
            shutil.copytree(root / name, work / name, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copyfile(root / "pytest-v3.ini", work / "pytest-v3.ini")
        source = work / "custom_components/heima/v3/runtime/producer_staging.py"
        original = source.read_text()
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "-c",
            "pytest-v3.ini",
            "tests/v3/runtime/test_producer_staging.py",
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
