#!/usr/bin/env python3
"""Live test for lighting tuning follow-up over an active admin-authored reaction."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.ha_client import HAApiError, HAClient


class HAFlowClient(HAClient):
    def options_flow_init(self, entry_id: str) -> dict[str, Any]:
        data = self.post("/api/config/config_entries/options/flow", {"handler": entry_id})
        if not isinstance(data, dict):
            raise HAApiError(f"invalid options flow init response: {type(data)}")
        return data

    def options_flow_configure(self, flow_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = self.post(f"/api/config/config_entries/options/flow/{flow_id}", payload)
        if not isinstance(data, dict):
            raise HAApiError(f"invalid options flow response: {type(data)}")
        return data

    def options_flow_abort(self, flow_id: str) -> None:
        self.delete(f"/api/config/config_entries/options/flow/{flow_id}")


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _expect_step(result: dict[str, Any], step_id: str) -> None:
    _assert(
        result.get("step_id") == step_id,
        f"expected step_id={step_id!r}, got={result.get('step_id')!r}: {result}",
    )


def _menu_next(client: HAFlowClient, flow_id: str, next_step_id: str) -> dict[str, Any]:
    return client.options_flow_configure(flow_id, {"next_step_id": next_step_id})


def _extract_select_values(step_result: dict[str, Any], field_name: str) -> list[str]:
    data_schema = step_result.get("data_schema")
    if not isinstance(data_schema, list):
        return []
    for field in data_schema:
        if not isinstance(field, dict) or str(field.get("name")) != field_name:
            continue
        values: list[str] = []
        options = field.get("options")
        if isinstance(options, list):
            for item in options:
                if isinstance(item, str):
                    values.append(item)
                elif isinstance(item, (list, tuple)) and item:
                    values.append(str(item[0]))
                elif isinstance(item, dict) and item.get("value") not in (None, ""):
                    values.append(str(item["value"]))
        elif isinstance(options, dict):
            values.extend(str(key) for key in options.keys())
        selector_cfg = field.get("selector")
        if isinstance(selector_cfg, dict):
            select_cfg = selector_cfg.get("select")
            if isinstance(select_cfg, dict):
                nested = select_cfg.get("options")
                if isinstance(nested, list):
                    for item in nested:
                        if isinstance(item, str):
                            values.append(item)
                        elif isinstance(item, (list, tuple)) and item:
                            values.append(str(item[0]))
                        elif isinstance(item, dict) and item.get("value") not in (None, ""):
                            values.append(str(item["value"]))
        return [value for value in values if value]
    return []


def _proposal_details(step_result: dict[str, Any]) -> str:
    placeholders = step_result.get("description_placeholders") or {}
    return str(placeholders.get("proposal_details") or "")


def _proposal_label(step_result: dict[str, Any]) -> str:
    placeholders = step_result.get("description_placeholders") or {}
    return str(placeholders.get("proposal_label") or "")


def _find_duplicate_error(step_result: dict[str, Any]) -> bool:
    errors = step_result.get("errors")
    return isinstance(errors, dict) and str(errors.get("base") or "") == "duplicate"


def _parse_hhmm(value: str) -> int:
    hh, mm = value.split(":", 1)
    return int(hh) * 60 + int(mm)


def _format_hhmm(minute: int) -> str:
    return f"{minute // 60:02d}:{minute % 60:02d}"


def _identity_key(room_id: str, weekday: int, minute: int) -> str:
    bucket = (minute // 30) * 30
    return f"lighting_scene_schedule|room={room_id}|weekday={weekday}|bucket={bucket}"


def _configured_reactions(entry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    options = entry.get("options")
    if not isinstance(options, dict):
        return {}
    reactions = options.get("reactions")
    if not isinstance(reactions, dict):
        return {}
    configured = reactions.get("configured")
    if not isinstance(configured, dict):
        return {}
    return {str(rid): dict(cfg) for rid, cfg in configured.items() if isinstance(cfg, dict)}


def _used_lighting_buckets(client: HAFlowClient, entry_id: str, room_id: str) -> set[int]:
    init = client.options_flow_init(entry_id)
    flow_id = str(init["flow_id"])
    try:
        _expect_step(init, "init")
        step = _menu_next(client, flow_id, "reactions_edit")
        if step.get("step_id") != "reactions_edit":
            return set()
        reaction_labels = _reaction_options_map(step)
        buckets: set[int] = set()
        prefix = f"Luci {room_id} — Lunedì ~"
        for label in reaction_labels.values():
            if not label.startswith(prefix):
                continue
            try:
                hhmm = label.split("~", 1)[1].split(" ", 1)[0]
                minute = _parse_hhmm(hhmm)
            except Exception:
                continue
            buckets.add((minute // 30) * 30)
        return buckets
    finally:
        time.sleep(0.1)
        try:
            client.options_flow_abort(flow_id)
        except Exception:
            pass


def _find_unused_lighting_slot(client: HAFlowClient, entry_id: str, room_id: str) -> tuple[str, int]:
    used_buckets = _used_lighting_buckets(client, entry_id, room_id)
    candidates = ["23:00", "22:30", "22:00", "21:30", "21:00", "20:30", "20:00", "19:30"]
    for hhmm in candidates:
        minute = _parse_hhmm(hhmm)
        bucket = (minute // 30) * 30
        if bucket not in used_buckets:
            return hhmm, minute
    raise AssertionError(f"no free lighting bucket found for room {room_id}")


def _proposal_diagnostics(client: HAClient, entry_id: str) -> dict[str, Any]:
    raw = client.get(f"/api/diagnostics/config_entry/{entry_id}")
    if not isinstance(raw, dict):
        return {}
    runtime = raw.get("data", {}).get("runtime", {})
    if not isinstance(runtime, dict):
        return {}
    proposals = runtime.get("proposals", {})
    return proposals if isinstance(proposals, dict) else {}


def _diagnostics_reactions_summary(client: HAClient, entry_id: str) -> dict[str, Any]:
    raw = client.get(f"/api/diagnostics/config_entry/{entry_id}")
    if not isinstance(raw, dict):
        return {}
    runtime = raw.get("data", {}).get("runtime", {})
    if not isinstance(runtime, dict):
        return {}
    plugins = runtime.get("plugins", {})
    if not isinstance(plugins, dict):
        return {}
    summary = plugins.get("configured_reaction_summary", {})
    return summary if isinstance(summary, dict) else {}


def _wait_for_reaction_count(
    client: HAClient,
    entry_id: str,
    *,
    expected_total: int,
    timeout_s: int,
    poll_s: float,
) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        summary = _diagnostics_reactions_summary(client, entry_id)
        if int(summary.get("total") or 0) == expected_total:
            return summary
        time.sleep(poll_s)
    raise AssertionError(
        f"configured_reaction_summary did not reach total={expected_total} within timeout"
    )


def _wait_for_tuning_proposal(
    client: HAClient,
    entry_id: str,
    *,
    identity_key: str,
    target_reaction_id: str | None,
    timeout_s: int,
    poll_s: float,
) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        client.call_service(
            "heima",
            "command",
            {"command": "learning_run", "target": {"entry_id": entry_id}},
        )
        diag = _proposal_diagnostics(client, entry_id)
        proposals = diag.get("proposals")
        if isinstance(proposals, list):
            for proposal in proposals:
                if not isinstance(proposal, dict):
                    continue
                if str(proposal.get("status") or "") != "pending":
                    continue
                if str(proposal.get("identity_key") or "") != identity_key:
                    continue
                if str(proposal.get("followup_kind") or "") != "tuning_suggestion":
                    continue
                if target_reaction_id and str(proposal.get("target_reaction_id") or "") != target_reaction_id:
                    continue
                return proposal
        time.sleep(poll_s)
    raise AssertionError("tuning follow-up proposal not visible in diagnostics within timeout")


def _seek_matching_tuning_review(
    client: HAFlowClient,
    flow_id: str,
    *,
    expected_description: str,
    max_steps: int = 12,
) -> dict[str, Any]:
    step = _menu_next(client, flow_id, "proposals")
    _expect_step(step, "proposals")
    for _ in range(max_steps):
        label = _proposal_label(step)
        details = _proposal_details(step)
        if expected_description in details or expected_description in label:
            return step
        step = client.options_flow_configure(flow_id, {"review_action": "skip"})
        if step.get("type") == "menu":
            break
        _expect_step(step, "proposals")
    raise AssertionError("matching tuning proposal not found in review queue")


def _reaction_options_map(step_result: dict[str, Any], field_name: str = "reaction") -> dict[str, str]:
    data_schema = step_result.get("data_schema")
    if not isinstance(data_schema, list):
        return {}
    for field in data_schema:
        if not isinstance(field, dict) or str(field.get("name")) != field_name:
            continue
        options = field.get("options")
        if isinstance(options, dict):
            return {str(key): str(value) for key, value in options.items()}
        if isinstance(options, list):
            out: dict[str, str] = {}
            for item in options:
                if isinstance(item, dict):
                    value = item.get("value")
                    label = item.get("label", value)
                    if value not in (None, ""):
                        out[str(value)] = str(label)
                elif isinstance(item, (list, tuple)) and item:
                    out[str(item[0])] = str(item[1] if len(item) > 1 else item[0])
                elif isinstance(item, str):
                    out[item] = item
            return out
    return {}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Heima lighting tuning follow-up live test"
    )
    parser.add_argument("--ha-url", required=True)
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--timeout-s", type=int, default=25)
    parser.add_argument("--poll-s", type=float, default=0.5)
    args = parser.parse_args()

    client = HAFlowClient(args.ha_url, args.ha_token, timeout_s=args.timeout_s)
    entry_id = client.find_heima_entry_id()
    print(f"Using heima entry_id={entry_id}")

    client.call_service("heima", "command", {"command": "learning_reset", "target": {"entry_id": entry_id}})

    init = client.options_flow_init(entry_id)
    flow_id = str(init["flow_id"])
    try:
        _expect_step(init, "init")

        step = _menu_next(client, flow_id, "admin_authored_create")
        _expect_step(step, "admin_authored_create")
        template_ids = _extract_select_values(step, "template_id")
        _assert(
            "lighting.scene_schedule.basic" in template_ids,
            f"lighting template not exposed: {template_ids}",
        )

        step = client.options_flow_configure(flow_id, {"template_id": "lighting.scene_schedule.basic"})
        _expect_step(step, "admin_authored_lighting_schedule")
        room_ids = _extract_select_values(step, "room_id")
        _assert(room_ids, "no room options available")
        room_id = "living" if "living" in room_ids else room_ids[0]
        authored_time, authored_minute = _find_unused_lighting_slot(client, entry_id, room_id)
        weekday = 0
        identity_key = _identity_key(room_id, weekday, authored_minute)
        print(f"Using authored slot: room={room_id} weekday={weekday} time={authored_time}")
        summary_before = _diagnostics_reactions_summary(client, entry_id)
        total_before = int(summary_before.get("total") or 0)
        known_reaction_ids = {str(item) for item in summary_before.get("reaction_ids") or []}

        step = client.options_flow_configure(
            flow_id,
            {
                "room_id": room_id,
                "weekday": str(weekday),
                "scheduled_time": authored_time,
                "light_entities": ["light.test_heima_living_main"],
                "action": "on",
                "brightness": 190,
                "color_temp_kelvin": 2850,
            },
        )
        if _find_duplicate_error(step):
            raise AssertionError(f"unexpected duplicate on chosen authored slot {authored_time}")
        _expect_step(step, "proposals")
        print("Admin-authored proposal created.")

        step = client.options_flow_configure(flow_id, {"review_action": "accept"})
        _assert(step.get("type") == "menu", f"unexpected accept result: {step}")
        client.call_service("homeassistant", "reload_config_entry", {"entry_id": entry_id})
        summary_after_authored = _wait_for_reaction_count(
            client,
            entry_id,
            expected_total=total_before + 1,
            timeout_s=args.timeout_s,
            poll_s=args.poll_s,
        )
        print(f"Reactions summary after authored accept: {summary_after_authored}")
        target_ids = sorted({str(item) for item in summary_after_authored.get("reaction_ids") or []} - known_reaction_ids)
        _assert(target_ids, "unable to identify newly configured authored reaction id")
        target_reaction_id = target_ids[0]
        print(f"Target reaction id: {target_reaction_id}")

        tuned_minute = authored_minute + 10
        client.call_service(
            "heima",
            "command",
            {
                "command": "seed_lighting_events",
                "target": {"entry_id": entry_id},
                "params": {
                    "entity_id": "light.test_heima_living_main",
                    "room_id": room_id,
                    "weekday": weekday,
                    "minute": tuned_minute,
                    "count": 5,
                    "brightness": 160,
                    "color_temp_kelvin": 2600,
                },
            },
        )
        print(f"Seeded learned lighting events for minute={tuned_minute}")

        tuning = _wait_for_tuning_proposal(
            client,
            entry_id,
            identity_key=identity_key,
            target_reaction_id=None,
            timeout_s=args.timeout_s,
            poll_s=args.poll_s,
        )
        print(f"Tuning proposal found: {tuning.get('id')}")
        print(f"Tuning proposal diagnostics: {tuning}")

        tuning_flow = client.options_flow_init(entry_id)
        tuning_flow_id = str(tuning_flow["flow_id"])
        try:
            _expect_step(tuning_flow, "init")
            review = _seek_matching_tuning_review(
                client,
                tuning_flow_id,
                expected_description=str(tuning.get("description") or ""),
            )
            label = _proposal_label(review)
            details = _proposal_details(review)
            print(f"Review label: {label}")
            print(f"Review details:\n{details}")
            _assert("Affinamento" in label or "Tuning" in label, "review title does not mark tuning")
            _assert(
                "automazione esistente" in details.lower()
                or "existing automation" in details.lower(),
                "review details do not describe tuning semantics",
            )
            expected_diff = f"{_format_hhmm(authored_minute)} -> {_format_hhmm(tuned_minute)}"
            _assert(
                f"Orario: {expected_diff}" in details
                or f"Time: {expected_diff}" in details,
                "review details do not show tuning diff",
            )

            result = client.options_flow_configure(tuning_flow_id, {"review_action": "accept"})
            _assert(result.get("type") == "menu", f"unexpected result after tuning accept: {result}")
        finally:
            time.sleep(0.1)
            try:
                client.options_flow_abort(tuning_flow_id)
            except Exception:
                pass

        client.call_service("homeassistant", "reload_config_entry", {"entry_id": entry_id})
        summary_after_tuning = _wait_for_reaction_count(
            client,
            entry_id,
            expected_total=total_before + 1,
            timeout_s=args.timeout_s,
            poll_s=args.poll_s,
        )
        print(f"Reactions summary after tuning accept: {summary_after_tuning}")

        edit_flow = client.options_flow_init(entry_id)
        edit_flow_id = str(edit_flow["flow_id"])
        try:
            _expect_step(edit_flow, "init")
            edit_step = _menu_next(client, edit_flow_id, "reactions_edit")
            _expect_step(edit_step, "reactions_edit")
            reaction_labels = _reaction_options_map(edit_step)
            _assert(target_reaction_id in reaction_labels, f"target reaction not present in reactions_edit: {reaction_labels}")
            target_label = reaction_labels[target_reaction_id]
        finally:
            time.sleep(0.1)
            try:
                client.options_flow_abort(edit_flow_id)
            except Exception:
                pass

        print(f"Reaction label after tuning: {target_label}")
        _assert(
            _format_hhmm(tuned_minute) in target_label,
            f"tuned reaction label does not expose updated time: {target_label}",
        )
        _assert(
            int((summary_after_tuning.get("by_origin") or {}).get("admin_authored") or 0)
            >= int((summary_after_authored.get("by_origin") or {}).get("admin_authored") or 0),
            "admin-authored reaction count regressed after tuning",
        )

        print("PASS: lighting tuning follow-up updated the existing admin-authored reaction")
        return 0
    finally:
        time.sleep(0.2)
        try:
            client.options_flow_abort(flow_id)
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
