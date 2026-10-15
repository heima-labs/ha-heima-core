"""Generation history records and canonical layer vocabulary mutations."""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MUTATIONS = (
    (
        "LayerGenerationRef_frozen",
        "@dataclass(frozen=True, slots=True)\nclass LayerGenerationRef:",
        "@dataclass(frozen=False, slots=True)\nclass LayerGenerationRef:",
        "test_records_are_frozen_slotted_hashable_and_replace_revalidates",
    ),
    (
        "LayerGenerationRef_slots",
        "@dataclass(frozen=True, slots=True)\nclass LayerGenerationRef:",
        "@dataclass(frozen=True, slots=False)\nclass LayerGenerationRef:",
        "test_records_are_frozen_slotted_hashable_and_replace_revalidates",
    ),
    (
        "ComposedGenerationManifest_frozen",
        "@dataclass(frozen=True, slots=True)\nclass ComposedGenerationManifest:",
        "@dataclass(frozen=False, slots=True)\nclass ComposedGenerationManifest:",
        "test_records_are_frozen_slotted_hashable_and_replace_revalidates",
    ),
    (
        "ComposedGenerationManifest_slots",
        "@dataclass(frozen=True, slots=True)\nclass ComposedGenerationManifest:",
        "@dataclass(frozen=True, slots=False)\nclass ComposedGenerationManifest:",
        "test_records_are_frozen_slotted_hashable_and_replace_revalidates",
    ),
    (
        "swap_canonical_layers_0",
        "_LAYER_ORDER = get_args(ConfigurationLayer.__value__)",
        "_LAYER_ORDER = ('layer3', 'layer2', 'layer4', 'layer5', 'layer6')",
        "test_exact_history_envelopes_and_canonical_layer_order",
    ),
    (
        "swap_canonical_layers_1",
        "_LAYER_ORDER = get_args(ConfigurationLayer.__value__)",
        "_LAYER_ORDER = ('layer2', 'layer4', 'layer3', 'layer5', 'layer6')",
        "test_exact_history_envelopes_and_canonical_layer_order",
    ),
    (
        "swap_canonical_layers_2",
        "_LAYER_ORDER = get_args(ConfigurationLayer.__value__)",
        "_LAYER_ORDER = ('layer2', 'layer3', 'layer5', 'layer4', 'layer6')",
        "test_exact_history_envelopes_and_canonical_layer_order",
    ),
    (
        "swap_canonical_layers_3",
        "_LAYER_ORDER = get_args(ConfigurationLayer.__value__)",
        "_LAYER_ORDER = ('layer2', 'layer3', 'layer4', 'layer6', 'layer5')",
        "test_exact_history_envelopes_and_canonical_layer_order",
    ),
    (
        "admit_unconfigured_layer7",
        'type ConfigurationLayer = Literal["layer2", "layer3", "layer4", "layer5", "layer6"]',
        'type ConfigurationLayer = Literal["layer2", "layer3", "layer4", "layer5", "layer6", "layer7"]',
        "test_closed_configuration_layer_vocabulary",
    ),
    (
        "skip_effective_instant_validation",
        "parse_instant(self.effective_at)",
        "None",
        "test_effective_at_must_be_one_canonical_instant",
    ),
    (
        "skip_unicode_validation",
        "canonical_json_bytes(value)",
        "None",
        "test_manifest_essential_text_fields_reject",
    ),
    (
        "skip_reference_revalidation",
        "LayerGenerationRef.__post_init__(ref)",
        "None",
        "test_tampered_reference_is_revalidated_at_manifest_boundary",
    ),
)


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="heima-generation-contract-mutations-") as directory:
        work = Path(directory)
        for name in ("custom_components", "tests"):
            shutil.copytree(root / name, work / name, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copyfile(root / "pytest-v3.ini", work / "pytest-v3.ini")
        source = work / "custom_components/heima/v3/contracts/generations.py"
        original = source.read_text()
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "-c",
            "pytest-v3.ini",
            "tests/v3/contracts/test_generations.py",
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
