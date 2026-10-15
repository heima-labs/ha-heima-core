"""Location immutable-value and semantic identity mutations."""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MUTATIONS = (
    (
        "mutable_location",
        "@dataclass(frozen=True, slots=True, eq=False)",
        "@dataclass(frozen=False, slots=True, eq=False)",
        "test_key_encoder_requires_location_and_value_remains_immutable",
    ),
    (
        "dynamic_location_shape",
        "@dataclass(frozen=True, slots=True, eq=False)",
        "@dataclass(frozen=True, slots=False, eq=False)",
        "test_key_encoder_requires_location_and_value_remains_immutable",
    ),
    (
        "utf16_order_for_semantic_room_set",
        "*sorted(location.room_ids)",
        '*sorted(location.room_ids, key=lambda item: item.encode("utf-16-be"))',
        "test_rooms_array_uses_codepoint_order_and_object_keys_still_use_utf16",
    ),
    (
        "ignore_identifier_in_equality",
        "return _location_key(self) == _location_key(other)",
        "return self.scope == other.scope",
        "test_property_opaque_identity_changes_exactly_when_id_changes",
    ),
    (
        "ignore_identifier_in_hash",
        "return hash(_location_key(self))",
        "return hash(self.scope)",
        "test_four_canonical_keys_equality_hash_and_json",
    ),
)


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="heima-location-mutations-") as directory:
        work = Path(directory)
        for name in ("custom_components", "tests"):
            shutil.copytree(root / name, work / name, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copyfile(root / "pytest-v3.ini", work / "pytest-v3.ini")
        source = work / "custom_components/heima/v3/contracts/location.py"
        original = source.read_text()
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "-c",
            "pytest-v3.ini",
            "tests/v3/contracts/test_location.py",
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
                "Location mutation baseline failed:\n" + baseline.stdout + baseline.stderr
            )
        for name, target, replacement, expected in MUTATIONS:
            if original.count(target) != 1:
                raise SystemExit("Location mutation target changed: " + name)
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
                    "Location mutation not killed as expected: "
                    + name
                    + "\n"
                    + result.stdout
                    + result.stderr
                )
            print(name + ": killed by " + expected)
        source.write_text(original)


if __name__ == "__main__":
    main()
