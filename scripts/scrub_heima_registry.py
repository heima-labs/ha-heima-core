#!/usr/bin/env python3
"""Remove Heima registry and storage data from a Home Assistant config dir.

This script is intended for factory-resetting Heima before a fresh install.
Run it while Home Assistant is stopped. It defaults to dry-run mode and only
writes files when --apply is passed.
"""

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

HEIMA_DOMAIN = "heima"
HEIMA_STORAGE_GLOB = "heima_*"
HEIMA_ENTITY_PREFIXES = ("sensor.heima_", "binary_sensor.heima_", "select.heima_")


class ChangeReport:
    def __init__(
        self,
        path: Path,
        action: str,
        removed: Optional[Dict[str, int]] = None,
        changed: bool = False,
    ) -> None:
        self.path = path
        self.action = action
        self.removed = removed or {}
        self.changed = changed

    def summary(self) -> str:
        details = ", ".join(f"{key}={value}" for key, value in sorted(self.removed.items()))
        suffix = f" ({details})" if details else ""
        return f"{self.action}: {self.path}{suffix}"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _entry_ids_from_config_entries(payload: Dict[str, Any]) -> Set[str]:
    entries = payload.get("data", {}).get("entries", [])
    return {
        str(entry.get("entry_id"))
        for entry in entries
        if isinstance(entry, dict) and str(entry.get("domain") or "") == HEIMA_DOMAIN
    }


def _is_heima_entity(entry: Any, heima_entry_ids: Set[str]) -> bool:
    if not isinstance(entry, dict):
        return False

    if str(entry.get("platform") or "") == HEIMA_DOMAIN:
        return True

    config_entry_ids = {str(item) for item in _as_list(entry.get("config_entry_id"))}
    if config_entry_ids & heima_entry_ids:
        return True

    entity_id = str(entry.get("entity_id") or "")
    return entity_id.startswith(HEIMA_ENTITY_PREFIXES)


def _is_heima_device(entry: Any, heima_entry_ids: Set[str]) -> bool:
    if not isinstance(entry, dict):
        return False

    identifiers = entry.get("identifiers") or []
    for identifier in identifiers:
        parts = [str(item) for item in _as_list(identifier)]
        if parts and parts[0] == HEIMA_DOMAIN:
            return True

    config_entry_ids = {str(item) for item in _as_list(entry.get("config_entries"))}
    if config_entry_ids & heima_entry_ids:
        return True

    primary_config_entry = str(entry.get("primary_config_entry") or "")
    if primary_config_entry in heima_entry_ids:
        return True

    manufacturer = str(entry.get("manufacturer") or "").lower()
    name = str(entry.get("name") or "").lower()
    return manufacturer == HEIMA_DOMAIN or name == HEIMA_DOMAIN


def _restore_state_entity_id(item: Any) -> str:
    if not isinstance(item, dict):
        return ""
    state = item.get("state")
    if not isinstance(state, dict):
        return ""
    return str(state.get("entity_id") or "")


def _is_heima_restore_state(item: Any) -> bool:
    entity_id = _restore_state_entity_id(item)
    return entity_id.startswith(HEIMA_ENTITY_PREFIXES)


def scrub_config_entries(storage_dir: Path) -> Tuple[Optional[ChangeReport], Set[str]]:
    path = storage_dir / "core.config_entries"
    if not path.exists():
        return None, set()

    payload = _load_json(path)
    heima_entry_ids = _entry_ids_from_config_entries(payload)
    data = payload.get("data", {})
    entries = list(data.get("entries") or [])
    kept = [
        entry
        for entry in entries
        if not (isinstance(entry, dict) and str(entry.get("domain") or "") == HEIMA_DOMAIN)
    ]
    removed = len(entries) - len(kept)
    if removed:
        data["entries"] = kept
        payload["data"] = data

    return (
        ChangeReport(
            path=path,
            action="update",
            removed={"config_entries": removed},
            changed=removed > 0,
        ),
        heima_entry_ids,
    )


def scrub_entity_registry(
    storage_dir: Path, heima_entry_ids: Set[str]
) -> Optional[ChangeReport]:
    path = storage_dir / "core.entity_registry"
    if not path.exists():
        return None

    payload = _load_json(path)
    data = payload.get("data", {})
    entities = list(data.get("entities") or [])
    deleted_entities = list(data.get("deleted_entities") or [])

    kept_entities = [entry for entry in entities if not _is_heima_entity(entry, heima_entry_ids)]
    kept_deleted = [
        entry for entry in deleted_entities if not _is_heima_entity(entry, heima_entry_ids)
    ]

    removed_entities = len(entities) - len(kept_entities)
    removed_deleted = len(deleted_entities) - len(kept_deleted)
    if removed_entities or removed_deleted:
        data["entities"] = kept_entities
        data["deleted_entities"] = kept_deleted
        payload["data"] = data

    return ChangeReport(
        path=path,
        action="update",
        removed={
            "entities": removed_entities,
            "deleted_entities": removed_deleted,
        },
        changed=bool(removed_entities or removed_deleted),
    )


def scrub_device_registry(
    storage_dir: Path, heima_entry_ids: Set[str]
) -> Optional[ChangeReport]:
    path = storage_dir / "core.device_registry"
    if not path.exists():
        return None

    payload = _load_json(path)
    data = payload.get("data", {})
    devices = list(data.get("devices") or [])
    deleted_devices = list(data.get("deleted_devices") or [])

    kept_devices = [entry for entry in devices if not _is_heima_device(entry, heima_entry_ids)]
    kept_deleted = [
        entry for entry in deleted_devices if not _is_heima_device(entry, heima_entry_ids)
    ]

    removed_devices = len(devices) - len(kept_devices)
    removed_deleted = len(deleted_devices) - len(kept_deleted)
    if removed_devices or removed_deleted:
        data["devices"] = kept_devices
        data["deleted_devices"] = kept_deleted
        payload["data"] = data

    return ChangeReport(
        path=path,
        action="update",
        removed={
            "devices": removed_devices,
            "deleted_devices": removed_deleted,
        },
        changed=bool(removed_devices or removed_deleted),
    )


def scrub_restore_state(storage_dir: Path) -> Optional[ChangeReport]:
    path = storage_dir / "core.restore_state"
    if not path.exists():
        return None

    payload = _load_json(path)
    data = payload.get("data")
    if not isinstance(data, list):
        return ChangeReport(path=path, action="skip", changed=False)

    kept = [item for item in data if not _is_heima_restore_state(item)]
    removed = len(data) - len(kept)
    if removed:
        payload["data"] = kept

    return ChangeReport(
        path=path,
        action="update",
        removed={"restore_states": removed},
        changed=removed > 0,
    )


def storage_file_reports(storage_dir: Path) -> List[ChangeReport]:
    return [
        ChangeReport(path=path, action="delete", changed=True)
        for path in sorted(storage_dir.glob(HEIMA_STORAGE_GLOB))
        if path.is_file()
    ]


def _backup_path(path: Path, backup_dir: Path) -> Path:
    return backup_dir / path.name


def _apply_change(report: ChangeReport, payload: Any, backup_dir: Path) -> None:
    if not report.changed:
        return
    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(report.path, _backup_path(report.path, backup_dir))
    if report.action == "delete":
        report.path.unlink()
    elif payload is not None:
        _write_json(report.path, payload)


def _collect_update_reports(
    storage_dir: Path, *, include_restore_state: bool
) -> Tuple[List[Tuple[ChangeReport, Any]], Set[str]]:
    reports = []  # type: List[Tuple[ChangeReport, Any]]

    config_report, heima_entry_ids = scrub_config_entries(storage_dir)
    if config_report is not None:
        reports.append((config_report, _load_json(config_report.path)))
        if config_report.changed:
            payload = _load_json(config_report.path)
            data = payload.get("data", {})
            data["entries"] = [
                entry
                for entry in list(data.get("entries") or [])
                if not (
                    isinstance(entry, dict)
                    and str(entry.get("domain") or "") == HEIMA_DOMAIN
                )
            ]
            payload["data"] = data
            reports[-1] = (config_report, payload)

    for scrubber in (scrub_entity_registry, scrub_device_registry):
        report = scrubber(storage_dir, heima_entry_ids)
        if report is None:
            continue
        payload = _load_json(report.path)
        if report.changed:
            payload = _scrub_payload_again(report.path, heima_entry_ids, include_restore_state)
        reports.append((report, payload))

    if include_restore_state:
        report = scrub_restore_state(storage_dir)
        if report is not None:
            payload = _load_json(report.path)
            if report.changed:
                payload = _scrub_payload_again(report.path, heima_entry_ids, include_restore_state)
            reports.append((report, payload))

    return reports, heima_entry_ids


def _scrub_payload_again(path: Path, heima_entry_ids: Set[str], include_restore_state: bool) -> Any:
    payload = _load_json(path)
    data = payload.get("data", {})
    if path.name == "core.entity_registry":
        data["entities"] = [
            entry
            for entry in list(data.get("entities") or [])
            if not _is_heima_entity(entry, heima_entry_ids)
        ]
        data["deleted_entities"] = [
            entry
            for entry in list(data.get("deleted_entities") or [])
            if not _is_heima_entity(entry, heima_entry_ids)
        ]
        payload["data"] = data
    elif path.name == "core.device_registry":
        data["devices"] = [
            entry
            for entry in list(data.get("devices") or [])
            if not _is_heima_device(entry, heima_entry_ids)
        ]
        data["deleted_devices"] = [
            entry
            for entry in list(data.get("deleted_devices") or [])
            if not _is_heima_device(entry, heima_entry_ids)
        ]
        payload["data"] = data
    elif include_restore_state and path.name == "core.restore_state":
        if isinstance(payload.get("data"), list):
            payload["data"] = [
                item for item in payload["data"] if not _is_heima_restore_state(item)
            ]
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Factory-reset Heima registry/storage data from a Home Assistant config dir."
    )
    parser.add_argument(
        "--config-dir",
        default="/config",
        help="Home Assistant config directory. Defaults to /config.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="Write changes to disk.")
    mode.add_argument("--dry-run", action="store_true", help="Preview changes only.")
    parser.add_argument(
        "--keep-restore-state",
        action="store_true",
        help="Do not remove Heima entries from core.restore_state.",
    )
    parser.add_argument(
        "--keep-heima-storage",
        action="store_true",
        help="Do not delete .storage/heima_* files.",
    )
    parser.add_argument(
        "--backup-dir",
        default=None,
        help="Backup directory used with --apply. Defaults to <config-dir>/heima_registry_backup_<timestamp>.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_dir = Path(args.config_dir).expanduser().resolve()
    storage_dir = config_dir / ".storage"
    apply = bool(args.apply)

    if not storage_dir.exists():
        print(f"error: storage directory not found: {storage_dir}")
        return 2

    updates, heima_entry_ids = _collect_update_reports(
        storage_dir, include_restore_state=not args.keep_restore_state
    )
    deletes = [] if args.keep_heima_storage else storage_file_reports(storage_dir)

    print("Heima registry scrub")
    print(f"- config_dir: {config_dir}")
    print(f"- mode: {'apply' if apply else 'dry-run'}")
    print(f"- heima_config_entry_ids: {sorted(heima_entry_ids) or 'none found'}")
    print("- warning: run with Home Assistant stopped before using --apply")

    changed_updates = [item for item in updates if item[0].changed]
    changed_reports = [report for report, _payload in changed_updates] + deletes
    if not changed_reports:
        print("No Heima registry or storage data found.")
        return 0

    print("\nPlanned changes:")
    for report in changed_reports:
        print(f"- {report.summary()}")

    if not apply:
        print("\nDry run only. Re-run with --apply to write changes.")
        return 0

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    backup_dir = (
        Path(args.backup_dir).expanduser().resolve()
        if args.backup_dir
        else config_dir / f"heima_registry_backup_{timestamp}"
    )

    for report, payload in changed_updates:
        _apply_change(report, payload, backup_dir)
    for report in deletes:
        _apply_change(report, None, backup_dir)

    print(f"\nApplied. Backups written to: {backup_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
