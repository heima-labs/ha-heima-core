#!/usr/bin/env python3
"""Live test: accept a pending darkness->contextual improvement proposal."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
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


def _proposal_label(step_result: dict[str, Any]) -> str:
    placeholders = step_result.get("description_placeholders") or {}
    return str(placeholders.get("proposal_label") or "")


def _proposal_details(step_result: dict[str, Any]) -> str:
    placeholders = step_result.get("description_placeholders") or {}
    return str(placeholders.get("proposal_details") or "")


def _diagnostics_root(client: HAClient, entry_id: str) -> dict[str, Any]:
    raw = client.get(f"/api/diagnostics/config_entry/{entry_id}")
    return raw if isinstance(raw, dict) else {}


def _proposal_diagnostics(client: HAClient, entry_id: str) -> dict[str, Any]:
    raw = _diagnostics_root(client, entry_id)
    runtime = raw.get("data", {}).get("runtime", {})
    if not isinstance(runtime, dict):
        return {}
    proposals = runtime.get("proposals", {})
    return proposals if isinstance(proposals, dict) else {}


def _configured_reactions(client: HAClient, entry_id: str) -> dict[str, dict[str, Any]]:
    raw = _diagnostics_root(client, entry_id)
    entry = raw.get("data", {}).get("entry", {})
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


def _find_pending_contextual_improvement(diag: dict[str, Any]) -> dict[str, Any] | None:
    proposals = diag.get("proposals")
    if not isinstance(proposals, list):
        return None
    for proposal in proposals:
        if not isinstance(proposal, dict):
            continue
        if str(proposal.get("type") or "") != "room_contextual_lighting_assist":
            continue
        if str(proposal.get("status") or "") != "pending":
            continue
        if str(proposal.get("followup_kind") or "") != "improvement":
            continue
        if str(proposal.get("target_reaction_type") or "") != "room_darkness_lighting_assist":
            continue
        return proposal
    return None


def _wait_for_pending_improvement(
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
        diag = _proposal_diagnostics(client, entry_id)
        found = _find_pending_contextual_improvement(diag)
        if found is not None:
            return found
        time.sleep(poll_s)
    raise AssertionError(
        "pending contextual improvement proposal not visible within timeout; "
        "precondition missing: ensure learning history already contains an accepted darkness "
        "proposal for the same room/slot."
    )


def _seek_matching_review(
    client: HAFlowClient,
    flow_id: str,
    *,
    proposal_id: str,
    target_reaction_id: str,
    max_steps: int = 24,
) -> dict[str, Any]:
    step = _menu_next(client, flow_id, "proposals")
    _expect_step(step, "proposals")
    for _ in range(max_steps):
        label = _proposal_label(step)
        details = _proposal_details(step)
        if (
            proposal_id in details
            or target_reaction_id in details
            or "Upgrade:" in label
            or "Miglioramento:" in label
        ):
            return step
        step = client.options_flow_configure(flow_id, {"review_action": "skip"})
        if step.get("type") == "menu":
            break
        _expect_step(step, "proposals")
    raise AssertionError("matching contextual improvement proposal not found in review queue")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Accept a pending darkness->contextual improvement proposal"
    )
    parser.add_argument("--ha-url", required=True)
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--timeout-s", type=int, default=60)
    parser.add_argument("--poll-s", type=float, default=0.5)
    args = parser.parse_args()

    client = HAFlowClient(args.ha_url, args.ha_token, timeout_s=args.timeout_s)
    entry_id = client.find_heima_entry_id()
    print(f"Using heima entry_id={entry_id}")

    pending = _wait_for_pending_improvement(
        client,
        entry_id,
        timeout_s=args.timeout_s,
        poll_s=args.poll_s,
    )
    proposal_id = str(pending.get("id") or "")
    target_reaction_id = str(pending.get("target_reaction_id") or "")
    print(f"Pending improvement proposal found: {proposal_id}")
    print(f"Target darkness reaction: {target_reaction_id}")

    before = _configured_reactions(client, entry_id)
    _assert(
        target_reaction_id in before, f"target reaction missing before accept: {target_reaction_id}"
    )
    _assert(
        str(before[target_reaction_id].get("reaction_type") or "")
        == "room_darkness_lighting_assist",
        f"target reaction is not darkness before accept: {before[target_reaction_id]}",
    )

    flow = client.options_flow_init(entry_id)
    flow_id = str(flow.get("flow_id") or "")
    try:
        review = _seek_matching_review(
            client,
            flow_id,
            proposal_id=proposal_id,
            target_reaction_id=target_reaction_id,
        )
        print(f"Proposal label:\n{_proposal_label(review)}")
        print(f"Proposal details:\n{_proposal_details(review)}")
        result = client.options_flow_configure(flow_id, {"review_action": "accept"})
        _assert(
            result.get("type") == "menu" and result.get("step_id") == "init",
            f"unexpected result after improvement accept: {result}",
        )
    finally:
        client.options_flow_abort(flow_id)

    after = _configured_reactions(client, entry_id)
    _assert(
        target_reaction_id in after, f"target reaction missing after accept: {target_reaction_id}"
    )
    cfg = after[target_reaction_id]
    _assert(
        str(cfg.get("reaction_type") or "") == "room_contextual_lighting_assist",
        f"target reaction not converted to contextual: {cfg}",
    )
    _assert(
        str(cfg.get("improved_from_reaction_type") or "") == "room_darkness_lighting_assist",
        f"improved_from_reaction_type not stored: {cfg}",
    )
    _assert(
        "entity_steps" not in cfg,
        f"darkness payload leaked into contextual contract: {cfg}",
    )
    print("PASS: improvement proposal converted darkness reaction into contextual reaction")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
