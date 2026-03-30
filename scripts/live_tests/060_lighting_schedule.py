#!/usr/bin/env python3
"""Seeded integration test for lighting proposal acceptance and schedule rebuild.

Pipeline tested:
  1. (optional) learning_reset        — wipe all learning data first
  2. optional real recording sanity   — toggle a real light entity and verify
                                        LightingRecorderBehavior captures the change
  3. seed_lighting_events             — inject deterministic history for the proposal gate
  4. reload config entry              → ProposalEngine.async_run()
  5. sensor + diagnostic check        → lighting_scene_schedule proposal pending
  6. accept proposal                  → options flow reactions/proposals step
  7. verify accepted status           → sensor poll / rebuild path

NOTE: this is not the canonical lighting-learning path anymore.
`025_lighting_learning_live.py` covers the real fixture-history + real-action
learning path. This script remains useful as a seeded regression for proposal
generation, acceptance, and rebuild behavior.

By default this script resets learning data first so the seeded regression is
deterministic and does not depend on proposals/events left behind by previous
live tests. Use `--no-reset` only for ad-hoc local experimentation.

Usage:
    python3 scripts/live_tests/060_lighting_schedule.py \\
        --ha-url http://127.0.0.1:8123 \\
        --ha-token <token> \\
        --light-entity light.test_heima_living_main \\
        --room-id living

    # Reuse current learning state instead of isolating the regression:
    python3 scripts/live_tests/060_lighting_schedule.py ... --no-reset
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.ha_client import HAApiError, HAClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_int(value: Any) -> int:
    raw = str(value or "").strip().lower()
    if raw in {"", "unknown", "unavailable", "none"}:
        return 0
    return int(float(raw))


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _proposals_attrs(client: HAClient, entity_id: str) -> dict[str, Any]:
    state = client.get_state(entity_id)
    return dict(state.get("attributes") or {})


def _proposal_diagnostics(client: HAClient, entry_id: str) -> dict[str, Any]:
    raw = client.get(f"/api/diagnostics/config_entry/{entry_id}")
    if not isinstance(raw, dict):
        return {}
    runtime = raw.get("data", {}).get("runtime", {})
    if not isinstance(runtime, dict):
        return {}
    proposals = runtime.get("proposals", {})
    return proposals if isinstance(proposals, dict) else {}


def _find_lighting_proposal(attrs: dict[str, Any], status: str = "pending") -> tuple[str, dict] | None:
    """Return (proposal_id, proposal_dict) for first lighting_scene_schedule with given status."""
    for pid, proposal in attrs.items():
        if not isinstance(proposal, dict):
            continue
        if (proposal.get("type") == "lighting_scene_schedule"
                and proposal.get("status") == status):
            return pid, proposal
    return None


def _find_lighting_proposal_by_config(
    attrs: dict[str, Any],
    *,
    room_id: str,
    weekday: int,
    minute: int,
    status: str,
) -> tuple[str, dict] | None:
    """Return matching lighting proposal by logical slot and status."""
    for pid, proposal in attrs.items():
        if not isinstance(proposal, dict):
            continue
        if proposal.get("type") != "lighting_scene_schedule":
            continue
        if proposal.get("status") != status:
            continue
        cfg = dict(proposal.get("config_summary") or {})
        if (
            str(cfg.get("room_id") or "") == room_id
            and int(cfg.get("weekday", -1)) == weekday
            and int(cfg.get("scheduled_min", -1)) == minute
        ):
            return pid, proposal
    return None


def _find_lighting_proposal_in_diag(
    diag: dict[str, Any],
    *,
    room_id: str,
    weekday: int,
    minute: int,
    statuses: set[str],
) -> tuple[str, dict[str, Any]] | None:
    proposals = diag.get("proposals")
    if not isinstance(proposals, list):
        return None
    for proposal in proposals:
        if not isinstance(proposal, dict):
            continue
        if proposal.get("type") != "lighting_scene_schedule":
            continue
        if str(proposal.get("status") or "") not in statuses:
            continue
        cfg = dict(proposal.get("config_summary") or {})
        if (
            str(cfg.get("room_id") or "") == room_id
            and int(cfg.get("weekday", -1)) == weekday
            and int(cfg.get("scheduled_min", -1)) == minute
        ):
            proposal_id = str(proposal.get("id") or "")
            if proposal_id:
                return proposal_id, proposal
    return None


def _wait_for_lighting_proposal(
    client: HAClient,
    entry_id: str,
    entity_id: str,
    *,
    room_id: str,
    weekday: int,
    minute: int,
    timeout_s: int,
    poll_s: float,
) -> tuple[str, dict]:
    """Poll until a matching pending proposal appears, or an accepted one already exists."""
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
        found_diag = _find_lighting_proposal_in_diag(
            diag,
            room_id=room_id,
            weekday=weekday,
            minute=minute,
            statuses={"pending", "accepted"},
        )
        if found_diag is not None:
            return found_diag
        attrs = _proposals_attrs(client, entity_id)
        result = _find_lighting_proposal_by_config(
            attrs,
            room_id=room_id,
            weekday=weekday,
            minute=minute,
            status="pending",
        )
        if result is not None:
            return result
        result = _find_lighting_proposal_by_config(
            attrs,
            room_id=room_id,
            weekday=weekday,
            minute=minute,
            status="accepted",
        )
        if result is not None:
            return result
        time.sleep(poll_s)
    raise RuntimeError(
        f"Timeout: no matching lighting_scene_schedule proposal in {entity_id} after {timeout_s}s"
    )


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


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------

def step_reset_learning(client: HAClient, entry_id: str) -> None:
    print("  → learning_reset")
    client.call_service("heima", "command", {
        "command": "learning_reset",
        "target": {"entry_id": entry_id},
    })


def step_seed_events(
    client: HAClient,
    entry_id: str,
    light_entity: str,
    room_id: str,
    weekday: int,
    minute: int,
    brightness: int | None,
    color_temp_kelvin: int | None,
    count: int,
) -> None:
    print(f"  → seed_lighting_events: {count} eventi per {light_entity} (room={room_id} "
          f"weekday={weekday} minute={minute})")
    params: dict[str, Any] = {
        "entity_id": light_entity,
        "room_id": room_id,
        "weekday": weekday,
        "minute": minute,
        "count": count,
    }
    if brightness is not None:
        params["brightness"] = brightness
    if color_temp_kelvin is not None:
        params["color_temp_kelvin"] = color_temp_kelvin
    client.call_service("heima", "command", {
        "command": "seed_lighting_events",
        "target": {"entry_id": entry_id},
        "params": params,
    })


def step_verify_real_recording(
    client: HAClient,
    light_entity: str,
    event_store_entity: str,
    poll_s: float,
    timeout_s: int = 10,
) -> None:
    """Toggle the real light entity and verify LightingRecorderBehavior records the event.

    Requires:
    - The light entity to exist in HA
    - The corresponding room to have area_id set in Heima options (via recover_lighting_areas)
    - LightingRecorderBehavior to be subscribed to EVENT_STATE_CHANGED

    If the entity does not exist, the step is skipped with a warning.
    """
    if not client.entity_exists(light_entity):
        print(f"  → WARN: {light_entity} non trovata, skip verifica recording reale")
        return

    state_before = client.get_state(event_store_entity)
    attrs_before = state_before.get("attributes") or {}
    lighting_before = _to_int(attrs_before.get("lighting", 0))

    print(f"  → toggle {light_entity} per verificare LightingRecorderBehavior "
          f"(lighting events prima: {lighting_before})")

    # Turn on
    client.call_service("light", "turn_on", {"entity_id": light_entity})
    time.sleep(0.5)
    # Turn off
    client.call_service("light", "turn_off", {"entity_id": light_entity})

    # Poll for new lighting event
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        attrs = (client.get_state(event_store_entity).get("attributes") or {})
        lighting_after = _to_int(attrs.get("lighting", 0))
        if lighting_after > lighting_before:
            print(f"     OK: LightingRecorderBehavior ha registrato l'evento "
                  f"(lighting events: {lighting_before} → {lighting_after})")
            return
        time.sleep(poll_s)

    print(f"  → WARN: nessun nuovo lighting event in {timeout_s}s — "
          f"verificare che il room abbia area_id configurato e corrisponda all'area di {light_entity}")


def step_trigger_proposal_run(client: HAClient, entry_id: str) -> None:
    print("  → heima.command learning_run → ProposalEngine.async_run()")
    client.call_service(
        "heima",
        "command",
        {"command": "learning_run", "target": {"entry_id": entry_id}},
    )


def step_wait_for_proposal(
    client: HAClient,
    entry_id: str,
    proposals_entity: str,
    *,
    room_id: str,
    weekday: int,
    minute: int,
    timeout_s: int,
    poll_s: float,
) -> tuple[str, dict]:
    print(f"  → attesa proposta lighting_scene_schedule in {proposals_entity}")
    proposal_id, proposal = _wait_for_lighting_proposal(
        client,
        entry_id,
        proposals_entity,
        room_id=room_id,
        weekday=weekday,
        minute=minute,
        timeout_s=timeout_s,
        poll_s=poll_s,
    )
    conf = proposal.get("confidence", "?")
    desc = str(proposal.get("description", "")).strip()
    status = str(proposal.get("status") or "")
    print(f"     proposta trovata: id={proposal_id} status={status} confidence={conf} desc={desc!r}")
    return proposal_id, proposal


def step_diag_check(client: HAClient, proposals_entity: str, proposal_id: str) -> None:
    """Verify proposal details via sensor attributes (equivalent to 030 diagnostic check)."""
    print("  → verifica diagnostica proposta (stile 030)")
    attrs = _proposals_attrs(client, proposals_entity)
    proposal = attrs.get(proposal_id)
    _assert(isinstance(proposal, dict), f"proposta {proposal_id} non trovata negli attributi")
    _assert(proposal.get("type") == "lighting_scene_schedule",
            f"tipo proposta errato: {proposal.get('type')}")
    _assert(proposal.get("status") in {"pending", "accepted"},
            f"status atteso 'pending' o 'accepted', trovato: {proposal.get('status')}")
    conf = float(proposal.get("confidence", 0))
    _assert(conf >= 0.3, f"confidence troppo bassa: {conf}")
    analyzer = str(proposal.get("analyzer_id", ""))
    _assert(analyzer == "LightingPatternAnalyzer",
            f"analyzer_id errato: {analyzer!r}")
    print(f"     OK: type={proposal.get('type')} status={proposal.get('status')} "
          f"confidence={conf:.2f} analyzer={analyzer}")


def step_accept_proposal(
    client: HAFlowClient,
    entry_id: str,
    proposals_entity: str,
    proposal_id: str,
) -> None:
    current_attrs = _proposals_attrs(client, proposals_entity)
    current = current_attrs.get(proposal_id)
    if isinstance(current, dict) and current.get("status") == "accepted":
        print(f"  → proposta {proposal_id} già accepted, skip review flow")
        return

    print(f"  → accettazione proposta {proposal_id} via options flow")
    init = client.options_flow_init(entry_id)
    flow_id = str(init["flow_id"])
    _expect_step(init, "init")

    step = _menu_next(client, flow_id, "proposals")
    _expect_step(step, "proposals")

    safety = 0
    target_probe = _proposals_attrs(client, proposals_entity).get(proposal_id)
    _assert(isinstance(target_probe, dict), f"proposta target {proposal_id} non trovata nel sensore")

    while not _proposal_step_matches_target(step, target_probe):
        safety += 1
        _assert(safety <= 20, f"impossibile raggiungere la proposta target {proposal_id} nella review queue")
        step = client.options_flow_configure(flow_id, {"review_action": "skip"})
        if step.get("type") == "menu" and step.get("step_id") == "init":
            raise AssertionError(f"la review queue è terminata prima di trovare la proposta {proposal_id}")
        _expect_step(step, "proposals")

    result = client.options_flow_configure(flow_id, {"review_action": "accept"})
    if result.get("type") == "form":
        if result.get("step_id") == "proposal_configure_action":
            result = client.options_flow_configure(
                flow_id,
                {"action_entities": [], "pre_condition_min": 20},
            )
        elif result.get("step_id") == "proposals":
            client.options_flow_abort(flow_id)
            return
        else:
            _assert(False, f"unexpected form step after accept: {result}")

    if result.get("type") == "create_entry":
        return

    if result.get("type") == "menu" and result.get("step_id") == "init":
        client.options_flow_abort(flow_id)
        return

    _assert(False, f"unexpected options flow result after accept: {result}")


def step_verify_accepted(
    client: HAClient,
    proposals_entity: str,
    proposal_id: str,
    timeout_s: int,
    poll_s: float,
) -> None:
    print(f"  → verifica status=accepted per {proposal_id}")
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        attrs = _proposals_attrs(client, proposals_entity)
        proposal = attrs.get(proposal_id)
        if isinstance(proposal, dict) and proposal.get("status") == "accepted":
            print("     accepted confermato nel sensore")
            return
        time.sleep(poll_s)
    raise RuntimeError(f"Timeout: proposta {proposal_id} non accepted dopo {timeout_s}s")


def step_verify_other_proposals_intact(
    client: HAClient,
    proposals_entity: str,
    other_types: list[str],
) -> None:
    """Verify that proposals of other types (e.g. presence_preheat) were not destroyed."""
    if not other_types:
        return
    print(f"  → verifica che le proposte di tipo {other_types} siano intatte")
    attrs = _proposals_attrs(client, proposals_entity)
    for ptype in other_types:
        found = any(
            isinstance(p, dict) and p.get("type") == ptype
            for p in attrs.values()
        )
        if found:
            print(f"     OK: proposte '{ptype}' ancora presenti")
        else:
            print(f"     WARN: nessuna proposta '{ptype}' trovata (potrebbe non essere stata generata)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Heima seeded lighting proposal acceptance regression"
    )
    parser.add_argument("--ha-url", default="http://127.0.0.1:8123")
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--light-entity", default="light.test_heima_living_main",
                        help="HA entity_id della luce (default: test lab living)")
    parser.add_argument("--room-id", default="living", help="Heima room_id (default: living)")
    parser.add_argument("--weekday", type=int, default=0, help="0=Lun … 6=Dom")
    parser.add_argument("--minute", type=int, default=1200,
                        help="minuto del giorno (0-1439); default 1200=20:00")
    parser.add_argument("--brightness", type=int, default=None)
    parser.add_argument("--color-temp-kelvin", type=int, default=None)
    parser.add_argument("--event-count", type=int, default=6,
                        help="eventi sintetici da iniettare (min 5)")
    parser.add_argument("--timeout-s", type=int, default=120)
    parser.add_argument("--poll-s", type=float, default=1.0)
    parser.add_argument("--no-reset", action="store_true",
                        help="non eseguire learning_reset prima del seeding")
    parser.add_argument("--skip-accept", action="store_true",
                        help="salta lo step di accettazione proposta e fermati alla verifica pending")
    args = parser.parse_args()

    if args.event_count < 5:
        print("FAIL: --event-count deve essere >= 5 (gate analyzer)", file=sys.stderr)
        return 1

    client = HAFlowClient(base_url=args.ha_url, token=args.ha_token)
    proposals_entity = "sensor.heima_reaction_proposals"

    entry_id = client.find_heima_entry_id()
    print(f"Heima entry_id={entry_id}")
    print("Scenario: seeded lighting proposal generation + acceptance regression")

    count_before = _to_int(client.get_state(proposals_entity).get("state"))
    print(f"Proposte esistenti prima del test: {count_before}")

    # 1. Reset (opzionale)
    if not args.no_reset:
        step_reset_learning(client, entry_id)
    else:
        print("  → learning_reset saltato (usa --no-reset per riusare lo stato corrente)")

    # 2. Verifica recording reale: toggle della luce vera e verifica che
    #    LightingRecorderBehavior catturi l'evento via STATE_CHANGED
    #    (funziona solo se il room ha area_id configurato via recover_lighting_areas)
    step_verify_real_recording(
        client,
        light_entity=args.light_entity,
        event_store_entity="sensor.heima_event_store",
        poll_s=args.poll_s,
    )

    # 3. Seed eventi sintetici (per superare il gate _spans_min_weeks)
    step_seed_events(
        client,
        entry_id,
        light_entity=args.light_entity,
        room_id=args.room_id,
        weekday=args.weekday,
        minute=args.minute,
        brightness=args.brightness,
        color_temp_kelvin=args.color_temp_kelvin,
        count=args.event_count,
    )

    # 4. Trigger proposal run
    step_trigger_proposal_run(client, entry_id)

    # 5. Attesa proposta lighting
    proposal_id, proposal = step_wait_for_proposal(
        client,
        entry_id,
        proposals_entity,
        room_id=args.room_id,
        weekday=args.weekday,
        minute=args.minute,
        timeout_s=args.timeout_s,
        poll_s=args.poll_s,
    )

    # 6. Verifica diagnostica (stile 030)
    step_diag_check(client, proposals_entity, proposal_id)

    if args.no_reset:
        # Verifica che le proposte di altri tipi non siano state distrutte
        step_verify_other_proposals_intact(client, proposals_entity, ["presence_preheat"])

    if args.skip_accept:
        print("PASS: seeded lighting proposal generated and verified (accept skipped)")
        return 0

    # 7. Accetta proposta
    step_accept_proposal(client, entry_id, proposals_entity, proposal_id)

    # 8. Verifica accepted
    step_verify_accepted(client, proposals_entity, proposal_id,
                         timeout_s=30, poll_s=args.poll_s)

    print("PASS: seeded lighting proposal accepted and rebuild path verified")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
