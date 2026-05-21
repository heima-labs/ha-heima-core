#!/usr/bin/env python3
# ruff: noqa: E402, I001
"""Live E2E check for positive outcome confidence boost."""

from __future__ import annotations

import argparse
from datetime import datetime
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


def _diagnostics_data(client: HAClient, entry_id: str) -> dict[str, Any]:
    raw = client.get(f"/api/diagnostics/config_entry/{entry_id}")
    if not isinstance(raw, dict):
        raise HAApiError(f"invalid diagnostics payload: {type(raw)}")
    data = raw.get("data")
    if not isinstance(data, dict):
        raise HAApiError("diagnostics payload missing data object")
    return data


def _proposal_diagnostics(client: HAClient, entry_id: str) -> list[dict[str, Any]]:
    runtime = _diagnostics_data(client, entry_id).get("runtime", {})
    proposals = runtime.get("proposals", {}) if isinstance(runtime, dict) else {}
    items = proposals.get("proposals", []) if isinstance(proposals, dict) else []
    return [dict(item) for item in items if isinstance(item, dict)]


def _outcome_diagnostics(client: HAClient, entry_id: str) -> dict[str, Any]:
    runtime = _diagnostics_data(client, entry_id).get("runtime", {})
    engine = runtime.get("engine", {}) if isinstance(runtime, dict) else {}
    outcome = engine.get("outcome_tracker", {}) if isinstance(engine, dict) else {}
    return dict(outcome) if isinstance(outcome, dict) else {}


def _proposal_by_id(client: HAClient, entry_id: str, proposal_id: str) -> dict[str, Any] | None:
    for proposal in _proposal_diagnostics(client, entry_id):
        if str(proposal.get("id") or "") == proposal_id:
            return proposal
    return None


def _find_presence_proposal(
    client: HAClient,
    entry_id: str,
    *,
    statuses: set[str],
) -> dict[str, Any] | None:
    for proposal in _proposal_diagnostics(client, entry_id):
        if str(proposal.get("type") or "") != "presence_preheat":
            continue
        if str(proposal.get("status") or "") not in statuses:
            continue
        proposal_id = str(proposal.get("id") or "")
        if proposal_id:
            return proposal
    return None


def _wait_for_presence_proposal(
    client: HAClient,
    entry_id: str,
    *,
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
        proposal = _find_presence_proposal(client, entry_id, statuses={"pending", "accepted"})
        if proposal is not None:
            return proposal
        time.sleep(poll_s)
    raise AssertionError("presence_preheat proposal not visible within timeout")


def _accept_presence_proposal(
    client: HAFlowClient,
    entry_id: str,
    proposal: dict[str, Any],
) -> str:
    proposal_id = str(proposal.get("id") or "")
    _assert(proposal_id, f"proposal id missing: {proposal}")
    if str(proposal.get("status") or "") == "accepted":
        return proposal_id

    init = client.options_flow_init(entry_id)
    flow_id = str(init.get("flow_id") or "")
    try:
        _expect_step(init, "init")
        step = client.options_flow_configure(flow_id, {"next_step_id": "proposals"})
        _expect_step(step, "proposals")

        for _ in range(30):
            if _proposal_step_matches(step, proposal):
                break
            step = client.options_flow_configure(flow_id, {"review_action": "skip"})
            if step.get("type") == "menu" and step.get("step_id") == "init":
                raise AssertionError("review queue ended before presence proposal")
            _expect_step(step, "proposals")
        else:
            raise AssertionError(f"proposal {proposal_id} not reachable in review queue")

        result = client.options_flow_configure(flow_id, {"review_action": "accept"})
        if result.get("type") == "form" and result.get("step_id") == "proposal_configure_action":
            result = client.options_flow_configure(
                flow_id,
                {"action_entities": [], "pre_condition_min": 1},
            )
        if result.get("type") in {"create_entry", "menu"}:
            return proposal_id
        raise AssertionError(f"unexpected result after accepting proposal: {result}")
    finally:
        client.options_flow_abort(flow_id)


def _proposal_step_matches(step: dict[str, Any], proposal: dict[str, Any]) -> bool:
    proposal_id = str(proposal.get("id") or "")
    description = str(proposal.get("description") or "")
    placeholders = step.get("description_placeholders") or {}
    text = "\n".join(str(value or "") for value in placeholders.values())
    return bool(
        (proposal_id and proposal_id in text)
        or (description and description[:32] in text)
        or (
            str(proposal.get("type") or "") == "presence_preheat"
            and "presence_preheat" in text
        )
    )


def _wait_for_accepted_target(
    client: HAClient,
    entry_id: str,
    proposal_id: str,
    *,
    timeout_s: int,
    poll_s: float,
) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    last: dict[str, Any] | None = None
    while time.time() < deadline:
        last = _proposal_by_id(client, entry_id, proposal_id)
        if (
            last is not None
            and str(last.get("status") or "") == "accepted"
            and str(last.get("target_reaction_id") or "") == proposal_id
        ):
            return last
        time.sleep(poll_s)
    raise AssertionError(f"accepted proposal did not expose self target: {last}")


def _state_int_from_value(value: Any) -> int:
    raw = str(value or "").strip().lower()
    if raw in {"unknown", "unavailable", "none", ""}:
        return 0
    return int(float(raw))


def _positive_streak(client: HAClient, entry_id: str, reaction_id: str) -> int:
    streaks = _outcome_diagnostics(client, entry_id).get("positive_streaks", {})
    if not isinstance(streaks, dict):
        return 0
    return _state_int_from_value(streaks.get(reaction_id))


def _records_count(client: HAClient, entry_id: str) -> int:
    return _state_int_from_value(_outcome_diagnostics(client, entry_id).get("records_count"))


def _build_due_presence_config(reaction_id: str, step_entity: str) -> dict[str, Any]:
    now = datetime.now().astimezone()
    current_min = now.hour * 60 + now.minute
    target_min = current_min + 1
    weekday = now.weekday()
    if target_min >= 1440:
        target_min -= 1440
        weekday = (weekday + 1) % 7
    return {
        "reaction_type": "presence_preheat",
        "enabled": True,
        "origin": "learned",
        "weekday": weekday,
        "median_arrival_min": target_min,
        "window_half_min": 30,
        "pre_condition_min": 1,
        "min_arrivals": 1,
        "steps": [
            {
                "domain": "input_boolean",
                "target": step_entity,
                "action": "input_boolean.turn_on",
                "params": {"entity_id": step_entity},
            }
        ],
        "source_proposal_id": reaction_id,
    }


def _seed_presence_history(client: HAClient) -> None:
    now = datetime.now().astimezone()
    weekday = now.weekday()
    first_minute = (now.hour * 60 + now.minute + 1) % 1440
    second_minute = (first_minute + 60) % 1440
    for minute in (first_minute, second_minute):
        client.call_service(
            "heima",
            "command",
            {
                "command": "seed_presence_events",
                "params": {
                    "weekday": weekday,
                    "minute": minute,
                    "count": 6,
                },
            },
        )


def _upsert_due_reaction(
    client: HAClient,
    *,
    reaction_id: str,
    step_entity: str,
) -> None:
    client.call_service(
        "heima",
        "command",
        {
            "command": "upsert_configured_reactions",
            "params": {
                "configured": {
                    reaction_id: _build_due_presence_config(reaction_id, step_entity)
                },
                "labels": {reaction_id: "Live positive outcome boost probe"},
            },
        },
    )


def _set_presence_source(
    client: HAClient,
    *,
    raw_entity: str,
    derived_entity: str,
    person_home_entity: str,
    state: str,
    timeout_s: int,
    poll_s: float,
) -> None:
    action = "turn_on" if state == "on" else "turn_off"
    expected_home = "on" if state == "on" else "off"
    client.call_service("input_boolean", action, {"entity_id": raw_entity})
    client.wait_state(derived_entity, state, timeout_s, poll_s)
    client.call_service("heima", "command", {"command": "recompute_now"})
    client.wait_state(person_home_entity, expected_home, timeout_s, poll_s)


def _drive_positive_outcomes(
    client: HAClient,
    entry_id: str,
    *,
    reaction_id: str,
    raw_entity: str,
    derived_entity: str,
    person_home_entity: str,
    step_entity: str,
    cycles: int,
    timeout_s: int,
    poll_s: float,
    settle_s: float,
) -> None:
    before_records = _records_count(client, entry_id)
    for idx in range(cycles):
        print(f"  outcome cycle {idx + 1}/{cycles}: fire while away")
        _set_presence_source(
            client,
            raw_entity=raw_entity,
            derived_entity=derived_entity,
            person_home_entity=person_home_entity,
            state="off",
            timeout_s=timeout_s,
            poll_s=poll_s,
        )
        client.call_service("input_boolean", "turn_off", {"entity_id": step_entity})
        client.call_service("heima", "command", {"command": "recompute_now"})
        time.sleep(settle_s)

        print(f"  outcome cycle {idx + 1}/{cycles}: resolve with arrival")
        _set_presence_source(
            client,
            raw_entity=raw_entity,
            derived_entity=derived_entity,
            person_home_entity=person_home_entity,
            state="on",
            timeout_s=timeout_s,
            poll_s=poll_s,
        )
        time.sleep(settle_s)

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if _records_count(client, entry_id) >= before_records + cycles:
            return
        time.sleep(poll_s)
    raise AssertionError(
        "positive outcome records did not grow as expected "
        f"(before={before_records}, after={_records_count(client, entry_id)})"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ha-url", required=True)
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--person-slug", default="test_user")
    parser.add_argument("--raw-entity", default="input_boolean.test_heima_room_studio_motion_raw")
    parser.add_argument("--derived-entity", default="binary_sensor.test_heima_room_studio_motion")
    parser.add_argument("--step-entity", default="input_boolean.test_heima_studio_fan_raw")
    parser.add_argument("--outcome-cycles", type=int, default=10)
    parser.add_argument("--settle-s", type=float, default=0.35)
    parser.add_argument("--timeout-s", type=int, default=90)
    parser.add_argument("--poll-s", type=float, default=0.5)
    args = parser.parse_args()

    client = HAFlowClient(args.ha_url, args.ha_token, timeout_s=args.timeout_s)
    entry_id = client.find_heima_entry_id()
    person_home_entity = f"binary_sensor.heima_person_{args.person_slug}_home"
    required = [
        "script.test_heima_reset",
        args.raw_entity,
        args.derived_entity,
        args.step_entity,
        person_home_entity,
    ]
    missing = [entity_id for entity_id in required if not client.entity_exists(entity_id)]
    _assert(not missing, "missing required entities:\n- " + "\n- ".join(missing))

    print(f"Using heima entry_id={entry_id}")
    print("Resetting lab runtime state without clearing learning fixtures...")
    client.call_service("script", "turn_on", {"entity_id": "script.test_heima_reset"})
    _set_presence_source(
        client,
        raw_entity=args.raw_entity,
        derived_entity=args.derived_entity,
        person_home_entity=person_home_entity,
        state="off",
        timeout_s=args.timeout_s,
        poll_s=args.poll_s,
    )

    print("Seeding multi-week presence history for a deterministic presence_preheat proposal...")
    _seed_presence_history(client)
    print("Looking for presence_preheat proposal...")
    proposal = _wait_for_presence_proposal(
        client,
        entry_id,
        timeout_s=args.timeout_s,
        poll_s=args.poll_s,
    )
    proposal_id = str(proposal.get("id") or "")
    print(f"Presence proposal ready: {proposal_id}")

    print("Accepting proposal through options flow...")
    _accept_presence_proposal(client, entry_id, proposal)
    accepted = _wait_for_accepted_target(
        client,
        entry_id,
        proposal_id,
        timeout_s=args.timeout_s,
        poll_s=args.poll_s,
    )
    before_confidence = float(accepted.get("confidence") or 0.0)
    print(f"Accepted proposal target={accepted.get('target_reaction_id')} confidence={before_confidence:.3f}")

    print("Configuring accepted presence reaction to fire now with a real non-empty step...")
    _upsert_due_reaction(client, reaction_id=proposal_id, step_entity=args.step_entity)
    client.call_service("homeassistant", "reload_config_entry", {"entry_id": entry_id})
    time.sleep(max(args.settle_s, 1.0))

    print("Driving positive outcomes through the real event recorder...")
    _drive_positive_outcomes(
        client,
        entry_id,
        reaction_id=proposal_id,
        raw_entity=args.raw_entity,
        derived_entity=args.derived_entity,
        person_home_entity=person_home_entity,
        step_entity=args.step_entity,
        cycles=args.outcome_cycles,
        timeout_s=args.timeout_s,
        poll_s=args.poll_s,
        settle_s=args.settle_s,
    )

    after = _proposal_by_id(client, entry_id, proposal_id)
    _assert(after is not None, f"accepted proposal disappeared: {proposal_id}")
    after_confidence = float(after.get("confidence") or 0.0)
    final_streak = _positive_streak(client, entry_id, proposal_id)
    _assert(final_streak == 0, f"positive streak should reset after boost, got {final_streak}")
    if before_confidence < 0.95:
        expected_confidence = min(1.0, before_confidence + 0.05)
        _assert(
            after_confidence + 0.000001 >= expected_confidence,
            f"confidence did not increase: before={before_confidence}, after={after_confidence}",
        )
    else:
        _assert(
            after_confidence == 1.0,
            f"confidence should remain capped at 1.0: before={before_confidence}, after={after_confidence}",
        )

    print(
        "PASS: positive outcomes reset streak and boosted/capped accepted proposal confidence "
        f"({before_confidence:.3f} -> {after_confidence:.3f})"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
