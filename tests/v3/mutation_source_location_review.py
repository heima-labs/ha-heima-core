"""Semantic dispatch and closed-source mutations for the critical review."""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MUTATIONS = (
    (
        "location.py",
        "virtual_validation",
        "Location.__post_init__(location)",
        "location.__post_init__()",
        "test_invalid_location_subclass_cannot_skip_base_shape_validation",
    ),
    (
        "location.py",
        "virtual_encoding",
        "canonical_json_bytes(_location_key(location))",
        "canonical_json_bytes(location.key)",
        "test_overridden_key_cannot_change_canonical_encoding_equality_or_hash",
    ),
    (
        "location.py",
        "virtual_equality",
        "return _location_key(self) == _location_key(other)",
        "return self.key == other.key",
        "test_overridden_key_cannot_change_canonical_encoding_equality_or_hash",
    ),
    (
        "location.py",
        "virtual_hash",
        "return hash(_location_key(self))",
        "return hash(self.key)",
        "test_overridden_key_cannot_change_canonical_encoding_equality_or_hash",
    ),
    (
        "fact_sources.py",
        "extended_runtime_source",
        "if type(source) not in (FactSource, ApplyStepSource):",
        "if not isinstance(source, (FactSource, ApplyStepSource)):",
        "test_extended_operational_source_is_rejected_before_serializing_person_fields",
    ),
    (
        "fact_sources.py",
        "extended_fingerprint_source",
        "if type(source) is not FactSource:",
        "if not isinstance(source, FactSource):",
        "test_extended_operational_source_is_rejected_before_serializing_person_fields",
    ),
)


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="heima-contract-review-mutations-") as directory:
        work = Path(directory)
        for name in ("custom_components", "tests"):
            shutil.copytree(root / name, work / name, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copyfile(root / "pytest-v3.ini", work / "pytest-v3.ini")
        sources = {
            name: work / "custom_components/heima/v3/contracts" / name
            for name in ("location.py", "fact_sources.py")
        }
        originals = {name: path.read_text() for name, path in sources.items()}
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "-c",
            "pytest-v3.ini",
            "tests/v3/contracts/test_location.py",
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
                "Contract review mutation baseline failed:\n" + baseline.stdout + baseline.stderr
            )
        for module, name, target, replacement, expected in MUTATIONS:
            source = sources[module]
            original = originals[module]
            if original.count(target) != 1:
                raise SystemExit("Contract review mutation target changed: " + name)
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
                    "Contract review mutation not killed as expected: "
                    + name
                    + "\n"
                    + result.stdout
                    + result.stderr
                )
            print(name + ": killed by " + expected)
            source.write_text(original)


if __name__ == "__main__":
    main()
