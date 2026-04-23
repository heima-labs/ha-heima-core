#!/usr/bin/env python3
"""Live E2E for context-conditioned lighting learning.

Strategy:
  1. reset learning for determinism
  2. remove pre-existing studio context-conditioned lighting reactions
  3. seed 4 positive studio scene episodes with strong abstract context active
  4. seed 4 negative comparable studio scene episodes with context inactive
  5. perform the 5th real scene occurrence through Home Assistant
  6. trigger learning and verify a pending context_conditioned_lighting_scene proposal
  7. accept the proposal and verify the configured reaction exists
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.ha_client import HAApiError, HAClient

TARGET_ROOM = "studio"
TARGET_CONTEXT_SIGNAL = "test_heima_studio_fan_context"
TARGET_LIGHTING_TYPE = "context_conditioned_lighting_scene"


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


def _to_int(value: Any) -> int:
    raw = str(value or "").strip().lower()
    if raw in {"", "unknown", "unavailable", "none"}:
        return 0
    return int(float(raw))


def _diagnostics_root(client: HAClient, entry_id: str) -> dict[str, Any]:
    raw = client.get(f"/api/diagnostics/config_entry/{entry_id}")
    return raw if isinstance(raw, dict) else {}


def _proposal_diagnostics(client: HAClient, entry_id: str) -> dict[str, Any]:
    runtime = _diagnostics_root(client, entry_id).get("data", {}).get("runtime", {})
    if not isinstance(runtime, dict):
        return {}
    proposals = runtime.get("proposals", {})
    return proposals if isinstance(proposals, dict) else {}


def _configured_reactions(client: HAClient, entry_id: str) -> dict[str, dict[str, Any]]:
    entry = _diagnostics_root(client, entry_id).get("data", {}).get("entry", {})
    if not isinstance(entry, dict):
        return {}
    options = entry.get("options", {})
    if not isinstance(options, dict):
        return {}
    reactions = options.get("reactions", {})
    if not isinstance(reactions, dict):
        return {}
    configured = reactions.get("configured", {})
    if not isinstance(configured, dict):
        return {}
    return {
        str(reaction_id): dict(cfg)
        for reaction_id, cfg in configured.items()
        if isinstance(cfg, dict)
    }


def _event_store_diagnostics(client: HAClient, entry_id: str) -> dict[str, Any]:
    runtime = _diagnostics_root(client, entry_id).get("data", {}).get("runtime", {})
    if not isinstance(runtime, dict):
        return {}
    event_store = runtime.get("event_store", {})
    return event_store if isinstance(event_store, dict) else {}


def _configured_context_lighting_reactions(
    client: HAClient,
    entry_id: str,
    *,
    weekday: int,
) -> list[tuple[str, dict[str, Any]]]:
    matches: list[tuple[str, dict[str, Any]]] = []
    for reaction_id, cfg in _configured_reactions(client, entry_id).items():
        if str(cfg.get("reaction_type") or "") != TARGET_LIGHTING_TYPE:
            continue
        if str(cfg.get("room_id") or "") != TARGET_ROOM:
            continue
        if int(cfg.get("weekday", -1)) != weekday:
            continue
        matches.append((reaction_id, cfg))
    return matches


def _menu_next(client: HAFlowClient, flow_id: str, next_step_id: str) -> dict[str, Any]:
    return client.options_flow_configure(flow_id, {"next_step_id": next_step_id})


def _expect_step(result: dict[str, Any], step_id: str) -> None:
    got = result.get("step_id")
    _assert(got == step_id, f"expected step_id={step_id!r}, got={got!r} — {result}")


def _proposal_step_matches_target(step: dict[str, Any], proposal: dict[str, Any]) -> bool:
    placeholders = dict(step.get("description_placeholders") or {})
    haystack = " ".join(
        str(placeholders.get(key) or "")
        for key in ("proposal_label", "proposal_details", "summary")
    )
    desc = str(proposal.get("description") or "").strip()
    return bool(desc) and desc in haystack


def _delete_reaction_via_flow(client: HAFlowClient, entry_id: str, reaction_id: str) -> None:
    init = client.options_flow_init(entry_id)
    flow_id = str(init.get("flow_id") or "")
    try:
        step = _menu_next(client, flow_id, "reactions_edit")
        _expect_step(step, "reactions_edit")
        step = client.options_flow_configure(flow_id, {"reaction": reaction_id})
        _assert(
            str(step.get("step_id") or "").startswith("reactions_edit"),
            f"unexpected edit step for delete: {step}",
        )
        payload = {"delete_reaction": True}
        data_schema = step.get("data_schema")
        if isinstance(data_schema, list):
            names = {
                str(field.get("name") or "") for field in data_schema if isinstance(field, dict)
            }
            if "enabled" in names:
                payload["enabled"] = bool(
                    _configured_reactions(client, entry_id)
                    .get(reaction_id, {})
                    .get("enabled", True)
                )
            if "weekday" in names:
                payload["weekday"] = datetime.now().weekday()
            if "scheduled_time" in names:
                payload["scheduled_time"] = "21:00"
        step = client.options_flow_configure(flow_id, payload)
        _expect_step(step, "reactions_delete_confirm")
        step = client.options_flow_configure(flow_id, {"confirm": True})
        _assert(
            step.get("type") == "menu" and step.get("step_id") == "init",
            f"unexpected result after delete confirm: {step}",
        )
    finally:
        client.options_flow_abort(flow_id)


def _wait_for_lighting_count_growth(
    client: HAClient,
    entry_id: str,
    previous: int,
    timeout_s: int,
    poll_s: float,
) -> int:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        diag = _event_store_diagnostics(client, entry_id)
        current = _to_int((diag.get("by_type", {}) or {}).get("lighting"))
        if current >= previous + 1:
            return current
        time.sleep(poll_s)
    diag = _event_store_diagnostics(client, entry_id)
    current = _to_int((diag.get("by_type", {}) or {}).get("lighting"))
    raise AssertionError(
        f"timeout waiting live lighting events to grow by 1 (before={previous}, after={current})"
    )


def _recompute(client: HAClient, entry_id: str) -> None:
    client.call_service(
        "heima", "command", {"command": "recompute_now", "target": {"entry_id": entry_id}}
    )


def _find_context_conditioned_lighting_proposal(
    diag: dict[str, Any],
    *,
    weekday: int,
) -> dict[str, Any] | None:
    proposals = diag.get("proposals")
    if not isinstance(proposals, list):
        return None
    for proposal in proposals:
        if not isinstance(proposal, dict):
            continue
        if str(proposal.get("type") or "") != TARGET_LIGHTING_TYPE:
            continue
        if str(proposal.get("status") or "") != "pending":
            continue
        cfg = dict(proposal.get("config_summary") or {})
        if str(cfg.get("room_id") or "") != TARGET_ROOM:
            continue
        if int(cfg.get("weekday", -1)) != weekday:
            continue
        return proposal
    return None


def _has_competing_schedule(diag: dict[str, Any], *, weekday: int, minute: int) -> bool:
    proposals = diag.get("proposals")
    if not isinstance(proposals, list):
        return False
    for proposal in proposals:
        if not isinstance(proposal, dict):
            continue
        if str(proposal.get("type") or "") != "lighting_scene_schedule":
            continue
        if str(proposal.get("status") or "") != "pending":
            continue
        cfg = dict(proposal.get("suggested_reaction_config") or {})
        if str(cfg.get("room_id") or "") != TARGET_ROOM:
            continue
        if int(cfg.get("weekday", -1)) != weekday:
            continue
        scheduled_min = int(cfg.get("scheduled_min", -9999))
        if abs(scheduled_min - minute) <= 5:
            return True
    return False


def _wait_for_context_conditioned_proposal(
    client: HAFlowClient,
    entry_id: str,
    *,
    weekday: int,
    minute: int,
    timeout_s: int,
    poll_s: float,
) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    last_trigger_at = 0.0
    while time.time() < deadline:
        now = time.time()
        if now - last_trigger_at >= max(5.0, poll_s):
            client.call_service(
                "heima",
                "command",
                {"command": "learning_run", "target": {"entry_id": entry_id}},
            )
            last_trigger_at = now
        diag = _proposal_diagnostics(client, entry_id)
        proposal = _find_context_conditioned_lighting_proposal(diag, weekday=weekday)
        if proposal is not None:
            _assert(
                not _has_competing_schedule(diag, weekday=weekday, minute=minute),
                "competing pending lighting_scene_schedule detected for same studio slot",
            )
            return proposal
        time.sleep(poll_s)
    raise AssertionError("pending context_conditioned_lighting_scene not visible within timeout")


def _accept_proposal(
    client: HAFlowClient,
    entry_id: str,
    proposals_entity: str,
    proposal_id: str,
) -> None:
    current = (
        client.get_state(proposals_entity).get("attributes", {}).get("items", {}).get(proposal_id)
    )
    _assert(isinstance(current, dict), f"proposal {proposal_id} not found in sensor")
    if current.get("status") == "accepted":
        return

    init = client.options_flow_init(entry_id)
    flow_id = str(init["flow_id"])
    try:
        _expect_step(init, "init")
        step = _menu_next(client, flow_id, "proposals")
        _expect_step(step, "proposals")

        safety = 0
        while not _proposal_step_matches_target(step, current):
            safety += 1
            _assert(safety <= 25, f"proposal {proposal_id} not reachable in review queue")
            step = client.options_flow_configure(flow_id, {"review_action": "skip"})
            if step.get("type") == "menu" and step.get("step_id") == "init":
                raise AssertionError("review queue ended before target proposal")
            _expect_step(step, "proposals")

        result = client.options_flow_configure(flow_id, {"review_action": "accept"})
        if result.get("type") == "form":
            if result.get("step_id") == "proposal_configure_action":
                result = client.options_flow_configure(
                    flow_id,
                    {"action_entities": [], "pre_condition_min": 20},
                )
            elif result.get("step_id") == "proposals":
                return
            else:
                raise AssertionError(f"unexpected form after accept: {result}")
        if result.get("type") == "create_entry":
            return
        if result.get("type") == "menu" and result.get("step_id") == "init":
            return
        raise AssertionError(f"unexpected options flow result after accept: {result}")
    finally:
        client.options_flow_abort(flow_id)


def _wait_for_accepted(
    client: HAClient,
    proposals_entity: str,
    proposal_id: str,
    timeout_s: int,
    poll_s: float,
) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        proposal = (
            client.get_state(proposals_entity)
            .get("attributes", {})
            .get("items", {})
            .get(proposal_id)
        )
        if isinstance(proposal, dict) and proposal.get("status") == "accepted":
            return
        time.sleep(poll_s)
    raise AssertionError(f"proposal {proposal_id} did not become accepted")


def main() -> int:
    parser = argparse.ArgumentParser(description="Heima live E2E for context-conditioned lighting")
    parser.add_argument("--ha-url", default="http://127.0.0.1:8123")
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--timeout-s", type=int, default=150)
    parser.add_argument("--poll-s", type=float, default=1.0)
    args = parser.parse_args()

    client = HAFlowClient(base_url=args.ha_url, token=args.ha_token)
    entry_id = client.find_heima_entry_id()
    print(f"Using heima entry_id={entry_id}")

    required = [
        "script.test_heima_reset",
        "light.test_heima_studio_desk",
        "light.test_heima_studio_spot",
        "switch.test_heima_studio_fan",
        "sensor.heima_reaction_proposals",
    ]
    missing = [entity_id for entity_id in required if not client.entity_exists(entity_id)]
    _assert(not missing, "Missing required entities:\n- " + "\n- ".join(missing))

    now = datetime.now()
    weekday = now.weekday()
    minute = now.hour * 60 + now.minute

    print("Resetting learning data...")
    client.call_service(
        "heima", "command", {"command": "learning_reset", "target": {"entry_id": entry_id}}
    )
    time.sleep(1.0)

    for reaction_id, _cfg in _configured_context_lighting_reactions(
        client, entry_id, weekday=weekday
    ):
        print(f"Cleaning pre-existing studio context-conditioned reaction: {reaction_id}")
        _delete_reaction_via_flow(client, entry_id, reaction_id)

    positive_steps = [
        {
            "entity_id": "light.test_heima_studio_desk",
            "action": "on",
            "brightness": 160,
            "color_temp_kelvin": 3300,
            "rgb_color": [255, 187, 129],
        },
    ]
    negative_steps = [
        {
            "entity_id": "light.test_heima_studio_spot",
            "action": "on",
            "brightness": 90,
            "color_temp_kelvin": 2700,
        }
    ]

    print("Seeding positive historical episodes with active context...")
    client.call_service(
        "heima",
        "command",
        {
            "command": "seed_lighting_scene_events",
            "target": {"entry_id": entry_id},
            "params": {
                "room_id": TARGET_ROOM,
                "weekday": weekday,
                "minute": minute,
                "count": 4,
                "signals": {"switch.test_heima_studio_fan": "on"},
                "entity_steps": positive_steps,
            },
        },
    )
    print("Seeding negative comparable episodes with inactive context...")
    client.call_service(
        "heima",
        "command",
        {
            "command": "seed_lighting_scene_events",
            "target": {"entry_id": entry_id},
            "params": {
                "room_id": TARGET_ROOM,
                "weekday": weekday,
                "minute": minute,
                "count": 4,
                "signals": {"switch.test_heima_studio_fan": "off"},
                "entity_steps": negative_steps,
            },
        },
    )

    lighting_before = _to_int(
        (_event_store_diagnostics(client, entry_id).get("by_type", {}) or {}).get("lighting")
    )

    print("Preparing lab state...")
    client.call_service("script", "turn_on", {"entity_id": "script.test_heima_reset"})
    client.wait_state("light.test_heima_studio_desk", "off", args.timeout_s, args.poll_s)
    client.wait_state("light.test_heima_studio_spot", "off", args.timeout_s, args.poll_s)
    _recompute(client, entry_id)
    time.sleep(0.5)

    print("Executing real context-conditioned studio scene...")
    client.call_service("switch", "turn_on", {"entity_id": "switch.test_heima_studio_fan"})
    client.wait_state("switch.test_heima_studio_fan", "on", args.timeout_s, args.poll_s)
    client.call_service(
        "light",
        "turn_on",
        {
            "entity_id": "light.test_heima_studio_desk",
            "brightness": 160,
            "color_temp_kelvin": 3300,
        },
    )
    client.wait_state("light.test_heima_studio_desk", "on", args.timeout_s, args.poll_s)

    lighting_after = _wait_for_lighting_count_growth(
        client, entry_id, lighting_before, args.timeout_s, args.poll_s
    )
    print(f"Lighting events after live scene: {lighting_after}")
    client.call_service("homeassistant", "reload_config_entry", {"entry_id": entry_id})
    time.sleep(2.0)

    proposal = _wait_for_context_conditioned_proposal(
        client,
        entry_id,
        weekday=weekday,
        minute=minute,
        timeout_s=args.timeout_s,
        poll_s=args.poll_s,
    )
    proposal_id = str(proposal.get("id") or "")
    _assert(proposal_id, f"proposal id missing: {proposal}")

    diagnostics = dict(proposal.get("explainability") or {})
    selected = dict(diagnostics.get("selected_context_condition") or {})
    _assert(selected, "context-conditioned proposal missing selected_context_condition")
    _assert(
        str(selected.get("signal_name") or "") == TARGET_CONTEXT_SIGNAL,
        f"unexpected context signal: {selected}",
    )
    _assert("concentration" in diagnostics, "missing concentration diagnostics")
    _assert("negative_episode_count" in diagnostics, "missing negative_episode_count diagnostics")
    _assert("contrast_status" in diagnostics, "missing contrast_status diagnostics")
    _assert(
        str(diagnostics.get("contrast_status") or "") == "verified",
        f"unexpected contrast_status: {diagnostics}",
    )
    _assert(
        _to_int(diagnostics.get("negative_episode_count")) >= 4,
        f"negative evidence too weak: {diagnostics}",
    )
    _assert(
        diagnostics.get("lift") is not None,
        f"expected verified proposal to expose lift: {diagnostics}",
    )

    print(f"Accepting proposal {proposal_id}...")
    _accept_proposal(client, entry_id, "sensor.heima_reaction_proposals", proposal_id)
    _wait_for_accepted(
        client, "sensor.heima_reaction_proposals", proposal_id, args.timeout_s, args.poll_s
    )

    configured = _configured_context_lighting_reactions(client, entry_id, weekday=weekday)
    _assert(configured, "accepted context-conditioned reaction not found in configured reactions")
    _configured_id, configured_cfg = configured[0]
    configured_conditions = list(configured_cfg.get("context_conditions") or [])
    _assert(configured_conditions, "configured reaction missing context_conditions")
    configured_first = dict(configured_conditions[0])
    _assert(
        str(configured_first.get("signal_name") or "") == TARGET_CONTEXT_SIGNAL,
        f"configured reaction has unexpected context signal: {configured_first}",
    )
    print("PASS: context-conditioned lighting proposal learned and accepted end-to-end")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
