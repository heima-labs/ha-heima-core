"""State buffer retention and order semantic mutation supplements."""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MUTATIONS = (
    (
        "default_horizon_removed",
        "_DEFAULT_HORIZON_SECONDS = 15 * 60",
        "_DEFAULT_HORIZON_SECONDS = 0",
        "test_horizon_default_floor_and_declared_extension",
    ),
    (
        "append_reversed",
        "stream.append(transition)",
        "stream.appendleft(transition)",
        "test_preserves_equal_time_transitions_and_reader_snapshot_after_eviction",
    ),
    (
        "evict_latest_instead_of_predecessor",
        "stream.popleft()",
        "stream.pop()",
        "test_eviction_boundary_uses_successor_not_old_record",
    ),
    (
        "mutable_reader_snapshot",
        "return tuple(self._stream(key))",
        "return self._stream(key)",
        "test_preserves_equal_time_transitions_and_reader_snapshot_after_eviction",
    ),
    (
        "forget_maintenance_boundary",
        "self._maintenance_when = now",
        "pass",
        "test_maintenance_and_late_append_reject_backward_clock_before_mutation",
    ),
    (
        "no_per_stream_extension",
        "Window(max(_DEFAULT_HORIZON_SECONDS, validated.seconds))",
        "Window(_DEFAULT_HORIZON_SECONDS)",
        "test_each_stream_extends_only_its_own_horizon_and_keeps_sparse_predecessor",
    ),
    (
        "own_horizons_not_shared",
        "self._horizons = MappingProxyType(owned)",
        "self._horizons = horizons",
        "test_owns_staged_horizons_and_empty_inventory_is_valid",
    ),
    (
        "forget_global_append_boundary",
        "self._last = transition",
        "pass",
        "test_append_order_is_global_across_streams_and_failed_append_does_not_consume_it",
    ),
)


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="heima-state-buffer-mutations-") as directory:
        work = Path(directory)
        for name in ("custom_components", "tests"):
            shutil.copytree(root / name, work / name, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copyfile(root / "pytest-v3.ini", work / "pytest-v3.ini")
        source = work / "custom_components/heima/v3/runtime/state_buffer.py"
        original = source.read_text()
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "-c",
            "pytest-v3.ini",
            "tests/v3/runtime/test_state_buffer.py",
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
                "Buffer mutation baseline failed:\n" + baseline.stdout + baseline.stderr
            )
        for name, target, replacement, expected in MUTATIONS:
            if original.count(target) != 1:
                raise SystemExit("Buffer mutation target changed: " + name)
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
                    "Buffer mutation not killed as expected: "
                    + name
                    + "\n"
                    + result.stdout
                    + result.stderr
                )
            print(name + ": killed by " + expected)
        source.write_text(original)


if __name__ == "__main__":
    main()
