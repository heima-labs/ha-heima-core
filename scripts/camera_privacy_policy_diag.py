#!/usr/bin/env python3
"""Read-only diagnostics for camera privacy policies."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.ha_client import HAApiError, HAClient


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _print_header(title: str) -> None:
    print(f"\n== {title} ==")


def _print_json(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, default=str))


def _state_summary(client: HAClient, entity_id: str) -> dict[str, Any]:
    if not entity_id:
        return {}
    try:
        state = client.get_state(entity_id)
    except HAApiError as err:
        return {"entity_id": entity_id, "error": str(err)}
    return {
        "entity_id": entity_id,
        "state": state.get("state"),
        "last_changed": state.get("last_changed"),
        "last_updated": state.get("last_updated"),
        "attributes": state.get("attributes") or {},
    }


def _diagnostics_data(client: HAClient, entry_id: str) -> dict[str, Any]:
    raw = client.get(f"/api/diagnostics/config_entry/{entry_id}")
    data = _as_dict(_as_dict(raw).get("data"))
    if not data:
        raise HAApiError("diagnostics payload missing data object")
    return data


def _camera_sources(security: dict[str, Any]) -> list[dict[str, Any]]:
    sources = security.get("camera_evidence_sources")
    if isinstance(sources, dict):
        return [
            {"id": str(source_id), **_as_dict(source)}
            for source_id, source in sources.items()
            if isinstance(source, dict)
        ]
    return [_as_dict(item) for item in _as_list(sources) if isinstance(item, dict)]


def _policy_matches(
    reaction_id: str,
    cfg: dict[str, Any],
    *,
    privacy_switch: str,
) -> bool:
    if not privacy_switch:
        return True
    metadata = _as_dict(cfg.get("camera_privacy_policy"))
    if str(metadata.get("privacy_entity") or "").strip() == privacy_switch:
        return True
    for step in _as_list(cfg.get("steps")):
        if not isinstance(step, dict):
            continue
        if str(step.get("target") or "").strip() == privacy_switch:
            return True
        params = _as_dict(step.get("params"))
        if str(params.get("entity_id") or "").strip() == privacy_switch:
            return True
    return privacy_switch in reaction_id


def _camera_policy_rows(
    reactions: dict[str, Any],
    *,
    privacy_switch: str,
) -> dict[str, dict[str, Any]]:
    configured = _as_dict(reactions.get("configured"))
    rows: dict[str, dict[str, Any]] = {}
    for reaction_id, raw_cfg in configured.items():
        cfg = _as_dict(raw_cfg)
        metadata = _as_dict(cfg.get("camera_privacy_policy"))
        source_template_id = str(cfg.get("source_template_id") or "")
        is_camera_policy = bool(metadata) or source_template_id == "security.camera_privacy_policy"
        if not is_camera_policy:
            continue
        if not _policy_matches(str(reaction_id), cfg, privacy_switch=privacy_switch):
            continue
        rows[str(reaction_id)] = cfg
    return rows


def _runtime_reaction_rows(
    runtime_engine: dict[str, Any],
    *,
    policy_ids: set[str],
    privacy_switch: str,
) -> dict[str, Any]:
    reactions = _as_dict(runtime_engine.get("reactions"))
    rows: dict[str, Any] = {}
    for reaction_id, cfg in reactions.items():
        text = json.dumps(cfg, default=str, sort_keys=True)
        if reaction_id in policy_ids or (privacy_switch and privacy_switch in text):
            rows[str(reaction_id)] = cfg
    return rows


def _manual_hold_rows(runtime_engine: dict[str, Any], *, privacy_switch: str) -> dict[str, Any]:
    manual_hold = _as_dict(runtime_engine.get("manual_hold"))
    if not privacy_switch:
        return manual_hold
    scope = f"switch:entity:{privacy_switch}"
    filtered = dict(manual_hold)
    active = [
        item
        for item in _as_list(manual_hold.get("active_holds"))
        if isinstance(item, dict) and str(item.get("scope") or "") == scope
    ]
    pending = _as_dict(manual_hold.get("pending_applies"))
    filtered["active_holds_for_privacy_switch"] = active
    filtered["pending_apply_for_privacy_switch"] = pending.get(scope)
    return filtered


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only camera privacy policy diagnostics")
    parser.add_argument("--ha-url", required=True)
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--alarm-entity", required=True)
    parser.add_argument("--privacy-switch", default="")
    parser.add_argument("--manual-hold-entity", default="")
    args = parser.parse_args()

    client = HAClient(base_url=args.ha_url, token=args.ha_token, timeout_s=30)
    entry_id = client.find_heima_entry_id()
    data = _diagnostics_data(client, entry_id)
    entry = _as_dict(data.get("entry"))
    options = _as_dict(entry.get("options"))
    security = _as_dict(options.get("security"))
    reactions = _as_dict(options.get("reactions"))
    runtime = _as_dict(data.get("runtime"))
    runtime_engine = _as_dict(runtime.get("engine"))

    policy_rows = _camera_policy_rows(
        reactions,
        privacy_switch=str(args.privacy_switch or "").strip(),
    )
    runtime_rows = _runtime_reaction_rows(
        runtime_engine,
        policy_ids=set(policy_rows),
        privacy_switch=str(args.privacy_switch or "").strip(),
    )

    _print_header("Inputs")
    _print_json(
        {
            "entry_id": entry_id,
            "alarm_entity": args.alarm_entity,
            "privacy_switch": args.privacy_switch,
            "manual_hold_entity": args.manual_hold_entity,
        }
    )

    _print_header("Entity States")
    states = {
        "alarm": _state_summary(client, args.alarm_entity),
    }
    if args.privacy_switch:
        states["privacy_switch"] = _state_summary(client, args.privacy_switch)
    if args.manual_hold_entity:
        states["manual_hold_entity"] = _state_summary(client, args.manual_hold_entity)
    _print_json(states)

    _print_header("Security Camera Sources")
    _print_json(_camera_sources(security))

    _print_header("Configured Camera Privacy Policies")
    _print_json(policy_rows)

    _print_header("Reactions Muted")
    _print_json(_as_list(reactions.get("muted")))

    _print_header("Runtime Matching Reactions")
    _print_json(runtime_rows)

    _print_header("Runtime Manual Hold")
    _print_json(
        _manual_hold_rows(
            runtime_engine,
            privacy_switch=str(args.privacy_switch or "").strip(),
        )
    )

    _print_header("Runtime Reaction Summary")
    _print_json(_as_dict(_as_dict(runtime.get("plugins")).get("configured_reaction_summary")))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
