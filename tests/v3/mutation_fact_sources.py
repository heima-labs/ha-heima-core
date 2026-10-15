"""Source vocabularies, data defaults and immutable shapes outside function mutation."""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MUTATIONS = (
    (
        "FactSource_frozen",
        "@dataclass(frozen=True, slots=True)\nclass FactSource:",
        "@dataclass(frozen=False, slots=True)\nclass FactSource:",
        "test_declared_source_values_are_frozen_and_slotted",
    ),
    (
        "FactSource_slots",
        "@dataclass(frozen=True, slots=True)\nclass FactSource:",
        "@dataclass(frozen=True, slots=False)\nclass FactSource:",
        "test_declared_source_values_are_frozen_and_slotted",
    ),
    (
        "ApplyStepSource_frozen",
        "@dataclass(frozen=True, slots=True)\nclass ApplyStepSource:",
        "@dataclass(frozen=False, slots=True)\nclass ApplyStepSource:",
        "test_declared_source_values_are_frozen_and_slotted",
    ),
    (
        "ApplyStepSource_slots",
        "@dataclass(frozen=True, slots=True)\nclass ApplyStepSource:",
        "@dataclass(frozen=True, slots=False)\nclass ApplyStepSource:",
        "test_declared_source_values_are_frozen_and_slotted",
    ),
    (
        "FactSourceFingerprint_frozen",
        "@dataclass(frozen=True, slots=True)\nclass FactSourceFingerprint:",
        "@dataclass(frozen=False, slots=True)\nclass FactSourceFingerprint:",
        "test_declared_source_values_are_frozen_and_slotted",
    ),
    (
        "FactSourceFingerprint_slots",
        "@dataclass(frozen=True, slots=True)\nclass FactSourceFingerprint:",
        "@dataclass(frozen=True, slots=False)\nclass FactSourceFingerprint:",
        "test_declared_source_values_are_frozen_and_slotted",
    ),
    (
        "fact_vocabulary",
        'FactSourceKind = Literal[\n    "sensor",',
        'FactSourceKind = Literal[\n    "fake_sensor",',
        "test_exact_fact_vocabulary",
    ),
    (
        "action_vocabulary",
        'ApplyStepSourceKind = Literal[\n    "reaction",',
        'ApplyStepSourceKind = Literal[\n    "sensor",\n    "reaction",',
        "test_fact_only_and_archive_kinds_are_never_action_sources",
    ),
    (
        "actor_vocabulary",
        'FactSourceActorType = Literal[\n    "ha_admin",',
        'FactSourceActorType = Literal[\n    "administrator",\n    "ha_admin",',
        "test_source_shape_rejects_wrong_fields_without_echoing_raw_data",
    ),
    (
        "FactSource_source_type_default",
        'class FactSource:\n    """Structured data only; construction never proves kind or actor authority."""\n\n    kind: FactSourceKind\n    source_id: str\n    source_type: str | None = None\n    configuration_fingerprint: str | None = None\n    route_fingerprint: str | None = None\n    actor_type: FactSourceActorType = "heima"\n    correlation_id: str = field(default_factory=lambda: str(uuid4()))\n\n',
        'class FactSource:\n    """Structured data only; construction never proves kind or actor authority."""\n\n    kind: FactSourceKind\n    source_id: str\n    source_type: str | None = ""\n    configuration_fingerprint: str | None = None\n    route_fingerprint: str | None = None\n    actor_type: FactSourceActorType = "heima"\n    correlation_id: str = field(default_factory=lambda: str(uuid4()))\n\n',
        "test_declared_defaults_and_uuid_safety_net",
    ),
    (
        "FactSource_configuration_fingerprint_default",
        'class FactSource:\n    """Structured data only; construction never proves kind or actor authority."""\n\n    kind: FactSourceKind\n    source_id: str\n    source_type: str | None = None\n    configuration_fingerprint: str | None = None\n    route_fingerprint: str | None = None\n    actor_type: FactSourceActorType = "heima"\n    correlation_id: str = field(default_factory=lambda: str(uuid4()))\n\n',
        'class FactSource:\n    """Structured data only; construction never proves kind or actor authority."""\n\n    kind: FactSourceKind\n    source_id: str\n    source_type: str | None = None\n    configuration_fingerprint: str | None = ""\n    route_fingerprint: str | None = None\n    actor_type: FactSourceActorType = "heima"\n    correlation_id: str = field(default_factory=lambda: str(uuid4()))\n\n',
        "test_declared_defaults_and_uuid_safety_net",
    ),
    (
        "FactSource_route_fingerprint_default",
        'class FactSource:\n    """Structured data only; construction never proves kind or actor authority."""\n\n    kind: FactSourceKind\n    source_id: str\n    source_type: str | None = None\n    configuration_fingerprint: str | None = None\n    route_fingerprint: str | None = None\n    actor_type: FactSourceActorType = "heima"\n    correlation_id: str = field(default_factory=lambda: str(uuid4()))\n\n',
        'class FactSource:\n    """Structured data only; construction never proves kind or actor authority."""\n\n    kind: FactSourceKind\n    source_id: str\n    source_type: str | None = None\n    configuration_fingerprint: str | None = None\n    route_fingerprint: str | None = ""\n    actor_type: FactSourceActorType = "heima"\n    correlation_id: str = field(default_factory=lambda: str(uuid4()))\n\n',
        "test_declared_defaults_and_uuid_safety_net",
    ),
    (
        "FactSource_actor_default",
        'class FactSource:\n    """Structured data only; construction never proves kind or actor authority."""\n\n    kind: FactSourceKind\n    source_id: str\n    source_type: str | None = None\n    configuration_fingerprint: str | None = None\n    route_fingerprint: str | None = None\n    actor_type: FactSourceActorType = "heima"\n    correlation_id: str = field(default_factory=lambda: str(uuid4()))\n\n',
        'class FactSource:\n    """Structured data only; construction never proves kind or actor authority."""\n\n    kind: FactSourceKind\n    source_id: str\n    source_type: str | None = None\n    configuration_fingerprint: str | None = None\n    route_fingerprint: str | None = None\n    actor_type: FactSourceActorType = "unknown"\n    correlation_id: str = field(default_factory=lambda: str(uuid4()))\n\n',
        "test_declared_defaults_and_uuid_safety_net",
    ),
    (
        "FactSource_causal_default",
        'class FactSource:\n    """Structured data only; construction never proves kind or actor authority."""\n\n    kind: FactSourceKind\n    source_id: str\n    source_type: str | None = None\n    configuration_fingerprint: str | None = None\n    route_fingerprint: str | None = None\n    actor_type: FactSourceActorType = "heima"\n    correlation_id: str = field(default_factory=lambda: str(uuid4()))\n\n',
        'class FactSource:\n    """Structured data only; construction never proves kind or actor authority."""\n\n    kind: FactSourceKind\n    source_id: str\n    source_type: str | None = None\n    configuration_fingerprint: str | None = None\n    route_fingerprint: str | None = None\n    actor_type: FactSourceActorType = "heima"\n    correlation_id: str = "fixed-id"\n\n',
        "test_declared_defaults_and_uuid_safety_net",
    ),
    (
        "ApplyStepSource_source_type_default",
        'class ApplyStepSource:\n    """Action-side source data; production paths explicitly propagate causal IDs."""\n\n    kind: ApplyStepSourceKind\n    source_id: str\n    source_type: str | None = None\n    configuration_fingerprint: str | None = None\n    actor_type: FactSourceActorType = "heima"\n    correlation_id: str = field(default_factory=lambda: str(uuid4()))\n\n',
        'class ApplyStepSource:\n    """Action-side source data; production paths explicitly propagate causal IDs."""\n\n    kind: ApplyStepSourceKind\n    source_id: str\n    source_type: str | None = ""\n    configuration_fingerprint: str | None = None\n    actor_type: FactSourceActorType = "heima"\n    correlation_id: str = field(default_factory=lambda: str(uuid4()))\n\n',
        "test_declared_defaults_and_uuid_safety_net",
    ),
    (
        "ApplyStepSource_configuration_fingerprint_default",
        'class ApplyStepSource:\n    """Action-side source data; production paths explicitly propagate causal IDs."""\n\n    kind: ApplyStepSourceKind\n    source_id: str\n    source_type: str | None = None\n    configuration_fingerprint: str | None = None\n    actor_type: FactSourceActorType = "heima"\n    correlation_id: str = field(default_factory=lambda: str(uuid4()))\n\n',
        'class ApplyStepSource:\n    """Action-side source data; production paths explicitly propagate causal IDs."""\n\n    kind: ApplyStepSourceKind\n    source_id: str\n    source_type: str | None = None\n    configuration_fingerprint: str | None = ""\n    actor_type: FactSourceActorType = "heima"\n    correlation_id: str = field(default_factory=lambda: str(uuid4()))\n\n',
        "test_declared_defaults_and_uuid_safety_net",
    ),
    (
        "ApplyStepSource_actor_default",
        'class ApplyStepSource:\n    """Action-side source data; production paths explicitly propagate causal IDs."""\n\n    kind: ApplyStepSourceKind\n    source_id: str\n    source_type: str | None = None\n    configuration_fingerprint: str | None = None\n    actor_type: FactSourceActorType = "heima"\n    correlation_id: str = field(default_factory=lambda: str(uuid4()))\n\n',
        'class ApplyStepSource:\n    """Action-side source data; production paths explicitly propagate causal IDs."""\n\n    kind: ApplyStepSourceKind\n    source_id: str\n    source_type: str | None = None\n    configuration_fingerprint: str | None = None\n    actor_type: FactSourceActorType = "unknown"\n    correlation_id: str = field(default_factory=lambda: str(uuid4()))\n\n',
        "test_declared_defaults_and_uuid_safety_net",
    ),
    (
        "ApplyStepSource_causal_default",
        'class ApplyStepSource:\n    """Action-side source data; production paths explicitly propagate causal IDs."""\n\n    kind: ApplyStepSourceKind\n    source_id: str\n    source_type: str | None = None\n    configuration_fingerprint: str | None = None\n    actor_type: FactSourceActorType = "heima"\n    correlation_id: str = field(default_factory=lambda: str(uuid4()))\n\n',
        'class ApplyStepSource:\n    """Action-side source data; production paths explicitly propagate causal IDs."""\n\n    kind: ApplyStepSourceKind\n    source_id: str\n    source_type: str | None = None\n    configuration_fingerprint: str | None = None\n    actor_type: FactSourceActorType = "heima"\n    correlation_id: str = "fixed-id"\n\n',
        "test_declared_defaults_and_uuid_safety_net",
    ),
)


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="heima-source-mutations-") as directory:
        work = Path(directory)
        for name in ("custom_components", "tests"):
            shutil.copytree(root / name, work / name, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copyfile(root / "pytest-v3.ini", work / "pytest-v3.ini")
        source = work / "custom_components/heima/v3/contracts/fact_sources.py"
        original = source.read_text()
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "-c",
            "pytest-v3.ini",
            "tests/v3/contracts/test_fact_sources.py",
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
                "Source mutation baseline failed:\n" + baseline.stdout + baseline.stderr
            )
        for name, target, replacement, expected in MUTATIONS:
            if original.count(target) != 1:
                raise SystemExit("Source mutation target changed: " + name)
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
                    "Source mutation not killed as expected: "
                    + name
                    + "\n"
                    + result.stdout
                    + result.stderr
                )
            print(name + ": killed by " + expected)
        source.write_text(original)


if __name__ == "__main__":
    main()
