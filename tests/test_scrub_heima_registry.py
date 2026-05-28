from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "scrub_heima_registry.py"


def _write_json(path: Path, payload: dict | list) -> None:
    path.write_text(json.dumps(payload))


def _read_json(path: Path):
    return json.loads(path.read_text())


def _build_storage(config_dir: Path) -> Path:
    storage = config_dir / ".storage"
    storage.mkdir()
    _write_json(
        storage / "core.config_entries",
        {
            "version": 1,
            "key": "core.config_entries",
            "data": {
                "entries": [
                    {"domain": "heima", "entry_id": "heima-entry", "title": "Heima"},
                    {"domain": "sun", "entry_id": "sun-entry", "title": "Sun"},
                ]
            },
        },
    )
    _write_json(
        storage / "core.entity_registry",
        {
            "version": 1,
            "key": "core.entity_registry",
            "data": {
                "entities": [
                    {
                        "entity_id": "sensor.heima_health",
                        "platform": "heima",
                        "config_entry_id": "heima-entry",
                    },
                    {
                        "entity_id": "sensor.heima_old",
                        "platform": "sensor",
                        "config_entry_id": None,
                    },
                    {
                        "entity_id": "sensor.sun_next_rising",
                        "platform": "sun",
                        "config_entry_id": "sun-entry",
                    },
                    {
                        "entity_id": "input_boolean.heima_manual_helper",
                        "platform": "input_boolean",
                        "config_entry_id": None,
                    },
                ],
                "deleted_entities": [
                    {
                        "entity_id": "binary_sensor.heima_anyone_home",
                        "platform": "heima",
                        "config_entry_id": "heima-entry",
                    },
                    {
                        "entity_id": "sensor.unrelated_deleted",
                        "platform": "test",
                        "config_entry_id": None,
                    },
                ],
            },
        },
    )
    _write_json(
        storage / "core.device_registry",
        {
            "version": 1,
            "key": "core.device_registry",
            "data": {
                "devices": [
                    {
                        "id": "heima-device",
                        "identifiers": [["heima", "heima-entry"]],
                        "config_entries": ["heima-entry"],
                    },
                    {
                        "id": "sun-device",
                        "identifiers": [["sun", "sun-entry"]],
                        "config_entries": ["sun-entry"],
                    },
                ],
                "deleted_devices": [
                    {
                        "id": "old-heima-device",
                        "manufacturer": "Heima",
                        "config_entries": [],
                    }
                ],
            },
        },
    )
    _write_json(
        storage / "core.restore_state",
        {
            "version": 1,
            "key": "core.restore_state",
            "data": [
                {"state": {"entity_id": "sensor.heima_health"}},
                {"state": {"entity_id": "input_boolean.heima_manual_helper"}},
                {"state": {"entity_id": "sensor.sun_next_rising"}},
            ],
        },
    )
    (storage / "heima_proposals").write_text("{}")
    return storage


def test_scrub_heima_registry_dry_run_does_not_modify(tmp_path: Path) -> None:
    storage = _build_storage(tmp_path)
    before = {path.name: path.read_text() for path in storage.iterdir()}

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--config-dir", str(tmp_path)],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "mode: dry-run" in result.stdout
    assert "Dry run only" in result.stdout
    assert {path.name: path.read_text() for path in storage.iterdir()} == before
    assert not list(tmp_path.glob("heima_registry_backup_*"))


def test_scrub_heima_registry_apply_removes_heima_only(tmp_path: Path) -> None:
    storage = _build_storage(tmp_path)

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--config-dir", str(tmp_path), "--apply"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "mode: apply" in result.stdout
    backups = list(tmp_path.glob("heima_registry_backup_*"))
    assert len(backups) == 1

    config_entries = _read_json(storage / "core.config_entries")
    assert [entry["domain"] for entry in config_entries["data"]["entries"]] == ["sun"]

    entity_registry = _read_json(storage / "core.entity_registry")
    assert [entry["entity_id"] for entry in entity_registry["data"]["entities"]] == [
        "sensor.sun_next_rising",
        "input_boolean.heima_manual_helper",
    ]
    assert [entry["entity_id"] for entry in entity_registry["data"]["deleted_entities"]] == [
        "sensor.unrelated_deleted"
    ]

    device_registry = _read_json(storage / "core.device_registry")
    assert [entry["id"] for entry in device_registry["data"]["devices"]] == ["sun-device"]
    assert device_registry["data"]["deleted_devices"] == []

    restore_state = _read_json(storage / "core.restore_state")
    assert [item["state"]["entity_id"] for item in restore_state["data"]] == [
        "input_boolean.heima_manual_helper",
        "sensor.sun_next_rising",
    ]
    assert not (storage / "heima_proposals").exists()
    assert (backups[0] / "heima_proposals").exists()
