#!/usr/bin/env python3
"""Live test for learned security presence simulation proposal + acceptance."""

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
    _assert(isinstance(result, dict), f"invalid flow result type: {type(result)}")
    _assert(
        result.get("step_id") == step_id,
        f"expected step_id={step_id!r}, got={result.get('step_id')!r}: {result}",
    )


def _menu_next(client: HAFlowClient, flow_id: str, next_step_id: str) -> dict[str, Any]:
    return client.options_flow_configure(flow_id, {"next_step_id": next_step_id})


def _to_int(value: Any) -> int:
    raw = str(value or "").strip().lower()
    if raw in {"", "unknown", "unavailable", "none"}:
        return 0
    return int(float(raw))


def _diagnostics_root(client: HAClient, entry_id: str) -> dict[str, Any]:
    raw = client.get(f"/api/diagnostics/config_entry/{entry_id}")
    return raw if isinstance(raw, dict) else {}


def _engine_reactions(client: HAClient, entry_id: str) -> dict[str, dict[str, Any]]:
    raw = _diagnostics_root(client, entry_id)
    runtime = raw.get("data", {}).get("runtime", {})
    engine = runtime.get("engine", {})
    reactions = engine.get("reactions", {})
    if not isinstance(reactions, dict):
        return {}
    return {str(k): dict(v) for k, v in reactions.items() if isinstance(v, dict)}


def _proposal_diagnostics(client: HAClient, entry_id: str) -> dict[str, Any]:
    raw = _diagnostics_root(client, entry_id)
    runtime = raw.get("data", {}).get("runtime", {})
    proposals = runtime.get("proposals", {})
    return proposals if isinstance(proposals, dict) else {}


def _event_store_diagnostics(client: HAClient, entry_id: str) -> dict[str, Any]:
    raw = _diagnostics_root(client, entry_id)
    runtime = raw.get("data", {}).get("runtime", {})
    event_store = runtime.get("event_store", {})
    return event_store if isinstance(event_store, dict) else {}


def _entry_options(client: HAClient, entry_id: str) -> dict[str, Any]:
    entry = client.get_entry(entry_id)
    options = entry.get("options", {})
    return dict(options) if isinstance(options, dict) else {}


def _configured_reactions(client: HAClient, entry_id: str) -> dict[str, dict[str, Any]]:
    raw = _diagnostics_root(client, entry_id)
    options = raw.get("data", {}).get("entry", {}).get("options", {})
    if not isinstance(options, dict):
        options = _entry_options(client, entry_id)
    reactions = dict(options.get("reactions", {}) or {})
    configured = reactions.get("configured", {})
    if not isinstance(configured, dict):
        return {}
    return {str(k): dict(v) for k, v in configured.items() if isinstance(v, dict)}


def _scheduler_pending_jobs(client: HAClient, entry_id: str) -> list[dict[str, Any]]:
    raw = _diagnostics_root(client, entry_id)
    runtime = raw.get("data", {}).get("runtime", {})
    scheduler = runtime.get("scheduler", {})
    pending = scheduler.get("pending_jobs", {})
    if isinstance(pending, list):
        return [item for item in pending if isinstance(item, dict)]
    return []


def _proposal_label(step: dict[str, Any]) -> str:
    return str(step.get("description_placeholders", {}).get("proposal_label") or "")


def _proposal_details(step: dict[str, Any]) -> str:
    return str(step.get("description_placeholders", {}).get("proposal_details") or "")


def _find_security_presence_proposal(diag: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    proposals = diag.get("proposals")
    if not isinstance(proposals, list):
        return None
    for proposal in proposals:
        if not isinstance(proposal, dict):
            continue
        if proposal.get("type") != "vacation_presence_simulation":
            continue
        if proposal.get("status") != "pending":
            continue
        if proposal.get("origin") != "learned":
            continue
        proposal_id = str(proposal.get("id") or "")
        if proposal_id:
            return proposal_id, proposal
    return None


def _wait_for_fixture_baseline(
    client: HAClient,
    entry_id: str,
    *,
    minimum: int,
    timeout_s: int,
    poll_s: float,
) -> int:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        diag = _event_store_diagnostics(client, entry_id)
        current = _to_int((diag.get("by_type", {}) or {}).get("lighting"))
        if current >= minimum:
            return current
        time.sleep(poll_s)
    diag = _event_store_diagnostics(client, entry_id)
    current = _to_int((diag.get("by_type", {}) or {}).get("lighting"))
    raise RuntimeError(
        "Lighting fixture baseline not loaded: "
        f"expected at least {minimum} historical lighting events, found {current}"
    )


def _wait_for_sun_context(
    client: HAClient,
    *,
    timeout_s: int,
    poll_s: float,
) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    last_state: dict[str, Any] | None = None
    while time.time() < deadline:
        try:
            state = client.get_state("sun.sun")
        except Exception:
            state = None
        if isinstance(state, dict):
            last_state = state
            raw_state = str(state.get("state") or "").strip().lower()
            attrs = dict(state.get("attributes") or {})
            if raw_state not in {"", "unknown", "unavailable"} and (
                attrs.get("next_setting") or attrs.get("next_rising")
            ):
                return state
        time.sleep(poll_s)
    raise AssertionError(f"sun.sun not ready in live lab: {last_state}")


def _wait_for_learned_proposal(
    client: HAClient,
    entry_id: str,
    *,
    timeout_s: int,
    poll_s: float,
) -> tuple[str, dict[str, Any]]:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        found = _find_security_presence_proposal(_proposal_diagnostics(client, entry_id))
        if found is not None:
            return found
        time.sleep(poll_s)
    raise AssertionError("pending learned vacation_presence_simulation proposal not visible within timeout")


def _seek_matching_review(
    client: HAFlowClient,
    flow_id: str,
    *,
    expected_phrase: str,
    max_steps: int = 20,
) -> dict[str, Any]:
    step = _menu_next(client, flow_id, "proposals")
    _expect_step(step, "proposals")
    for _ in range(max_steps):
        label = _proposal_label(step)
        details = _proposal_details(step)
        if expected_phrase in details or expected_phrase in label:
            return step
        step = client.options_flow_configure(flow_id, {"review_action": "skip"})
        if step.get("type") == "menu":
            break
        _expect_step(step, "proposals")
    raise AssertionError("matching learned security presence proposal not found in review queue")


def _accept_and_finalize_review_queue(
    client: HAFlowClient,
    flow_id: str,
) -> None:
    result = client.options_flow_configure(flow_id, {"review_action": "accept"})
    while True:
        if result.get("type") == "menu":
            _expect_step(result, "init")
            save = _menu_next(client, flow_id, "save")
            _assert(save.get("type") == "create_entry", f"expected create_entry on save, got: {save}")
            return
        if result.get("type") == "form":
            _expect_step(result, "proposals")
            result = client.options_flow_configure(flow_id, {"review_action": "skip"})
            continue
        raise AssertionError(f"unexpected options flow result while finalizing review queue: {result}")


def _first_person_override_entity(client: HAClient) -> str | None:
    for state in client.all_states():
        entity_id = str(state.get("entity_id") or "")
        if entity_id.startswith("select.heima_person_") and entity_id.endswith("_override"):
            return entity_id
    return None


def _set_person_override(client: HAClient, entity_id: str, option: str) -> None:
    client.call_service("select", "select_option", {"entity_id": entity_id, "option": option})


def _ensure_security_presence_learning_enabled(client: HAFlowClient, entry_id: str) -> None:
    options = _entry_options(client, entry_id)
    learning = dict(options.get("learning", {}) or {})
    enabled = [
        str(item).strip()
        for item in learning.get("enabled_plugin_families") or []
        if str(item).strip()
    ]
    required_families = {"lighting", "security_presence_simulation"}
    if required_families.issubset(set(enabled)):
        return

    for family in ("lighting", "security_presence_simulation"):
        if family not in enabled:
            enabled.append(family)
    payload = {
        "context_signal_entities": list(learning.get("context_signal_entities") or []),
        "enabled_plugin_families": enabled,
    }
    for key in ("outdoor_lux_entity", "outdoor_temp_entity", "weather_entity"):
        value = learning.get(key)
        if value not in (None, ""):
            payload[key] = value

    init = client.options_flow_init(entry_id)
    flow_id = str(init["flow_id"])
    try:
        _expect_step(init, "init")
        step = _menu_next(client, flow_id, "learning")
        _expect_step(step, "learning")
        result = client.options_flow_configure(flow_id, payload)
        _expect_step(result, "init")
        save = _menu_next(client, flow_id, "save")
        _assert(save.get("type") == "create_entry", f"expected create_entry on save, got: {save}")
    finally:
        time.sleep(0.2)
        try:
            client.options_flow_abort(flow_id)
        except Exception:
            pass


def _find_presence_reaction_id(
    client: HAClient,
    entry_id: str,
    *,
    proposal_id: str,
    identity_key: str,
) -> str | None:
    configured = _configured_reactions(client, entry_id)
    direct_match: str | None = None
    tuning_match: str | None = None
    fallback: str | None = None
    for reaction_id, cfg in configured.items():
        if str(cfg.get("reaction_class") or "") != "VacationPresenceSimulationReaction":
            continue
        if fallback is None:
            fallback = reaction_id
        if str(cfg.get("source_proposal_identity_key") or "").strip() == identity_key:
            direct_match = reaction_id
        if str(cfg.get("last_tuning_proposal_id") or "").strip() == proposal_id:
            tuning_match = reaction_id
    return tuning_match or direct_match or fallback


def _wait_configured_presence_reaction(
    client: HAClient,
    entry_id: str,
    *,
    proposal_id: str,
    identity_key: str,
    timeout_s: int,
    poll_s: float,
) -> str:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        reaction_id = _find_presence_reaction_id(
            client,
            entry_id,
            proposal_id=proposal_id,
            identity_key=identity_key,
        )
        if reaction_id:
            return reaction_id
        time.sleep(poll_s)
    raise AssertionError("accepted learned security presence reaction not visible in configured options")


def _wait_reaction_ready(
    client: HAClient,
    entry_id: str,
    *,
    reaction_id: str,
    timeout_s: int,
    poll_s: float,
) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    last_diag: dict[str, Any] | None = None
    while time.time() < deadline:
        diag = _engine_reactions(client, entry_id).get(reaction_id)
        if isinstance(diag, dict):
            last_diag = diag
            if (
                str(diag.get("source_profile_kind") or "") == "learned_source_profiles"
                and bool(diag.get("source_profile_ready"))
                and (
                    int(diag.get("tonight_plan_count") or 0) >= 1
                    or str(diag.get("blocked_reason") or "") in {
                        "awaiting_next_planned_activation",
                        "outside_not_dark",
                        "sun_unavailable",
                    }
                )
            ):
                return diag
        time.sleep(poll_s)
    raise AssertionError(
        "learned security presence reaction diagnostics not ready within timeout: "
        f"{last_diag}"
    )


def _wait_runtime_reaction_loaded(
    client: HAClient,
    entry_id: str,
    *,
    reaction_id: str,
    timeout_s: int,
    poll_s: float,
) -> dict[str, Any] | None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        diag = _engine_reactions(client, entry_id).get(reaction_id)
        if isinstance(diag, dict):
            return diag
        time.sleep(poll_s)
    return None


def _wait_scheduler_job(
    client: HAClient,
    entry_id: str,
    *,
    reaction_id: str,
    timeout_s: int,
    poll_s: float,
) -> dict[str, Any]:
    prefix = f"security_presence_simulation:{reaction_id}:"
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        for job in _scheduler_pending_jobs(client, entry_id):
            if str(job.get("job_id") or "").startswith(prefix):
                return job
        time.sleep(poll_s)
    raise AssertionError(f"scheduler job for {reaction_id!r} not visible within timeout")


def main() -> int:
    parser = argparse.ArgumentParser(description="Heima learned security presence simulation flow")
    parser.add_argument("--ha-url", required=True)
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--timeout-s", type=int, default=60)
    parser.add_argument("--poll-s", type=float, default=1.0)
    args = parser.parse_args()

    client = HAFlowClient(args.ha_url, args.ha_token, timeout_s=args.timeout_s)
    entry_id = client.find_heima_entry_id()
    person_override_entity = _first_person_override_entity(client)
    if not person_override_entity:
        raise AssertionError("no heima person override select found")

    print(f"Using heima entry_id={entry_id}")
    print(f"Using person override entity={person_override_entity}")

    _ensure_security_presence_learning_enabled(client, entry_id)
    lighting_before = _wait_for_fixture_baseline(
        client,
        entry_id,
        minimum=84,
        timeout_s=min(args.timeout_s, 60),
        poll_s=args.poll_s,
    )
    print(f"Lighting fixture baseline: {lighting_before}")
    sun_state = _wait_for_sun_context(
        client,
        timeout_s=min(args.timeout_s, 60),
        poll_s=args.poll_s,
    )
    print("Sun context ready:")
    print(sun_state)

    print("Reloading Heima config entry to trigger learned proposal run...")
    client.call_service("homeassistant", "reload_config_entry", {"entry_id": entry_id})

    proposal_id, proposal = _wait_for_learned_proposal(
        client,
        entry_id,
        timeout_s=args.timeout_s,
        poll_s=args.poll_s,
    )
    print(f"Pending learned proposal id={proposal_id}")
    print(proposal)

    identity_key = str(proposal.get("identity_key") or "")
    _assert(identity_key == "vacation_presence_simulation|scope=home", f"unexpected identity_key: {identity_key!r}")
    config_summary = dict(proposal.get("config_summary") or {})
    explainability = dict(proposal.get("explainability") or {})
    _assert(
        str(config_summary.get("reaction_class") or "") == "VacationPresenceSimulationReaction",
        f"unexpected reaction_class summary: {config_summary!r}",
    )
    _assert(
        str(explainability.get("plugin_family") or "") == "security_presence_simulation",
        f"unexpected explainability payload: {explainability!r}",
    )
    _assert(
        int(explainability.get("weeks_observed") or 0) >= 2,
        f"insufficient learned evidence in explainability: {explainability!r}",
    )

    init = client.options_flow_init(entry_id)
    flow_id = str(init["flow_id"])
    try:
        _expect_step(init, "init")
        step = _seek_matching_review(client, flow_id, expected_phrase="policy dinamica appresa")
        print("Review label:", _proposal_label(step))
        print("Review details:", _proposal_details(step))
        _accept_and_finalize_review_queue(client, flow_id)
    finally:
        time.sleep(0.2)
        try:
            client.options_flow_abort(flow_id)
        except Exception:
            pass

    reaction_id: str | None = None
    try:
        reaction_id = _wait_configured_presence_reaction(
            client,
            entry_id,
            proposal_id=proposal_id,
            identity_key=identity_key,
            timeout_s=max(5, min(args.timeout_s, 15)),
            poll_s=args.poll_s,
        )
    except AssertionError:
        print("Configured reaction not visible yet after save; forcing entry reload...")
        client.call_service("homeassistant", "reload_config_entry", {"entry_id": entry_id})
        reaction_id = _wait_configured_presence_reaction(
            client,
            entry_id,
            proposal_id=proposal_id,
            identity_key=identity_key,
            timeout_s=args.timeout_s,
            poll_s=args.poll_s,
        )
    print(f"Configured target reaction_id={reaction_id}")

    runtime_diag = _wait_runtime_reaction_loaded(
        client,
        entry_id,
        reaction_id=reaction_id,
        timeout_s=max(5, min(args.timeout_s, 15)),
        poll_s=args.poll_s,
    )
    if not runtime_diag or str(runtime_diag.get("source_profile_kind") or "") != "learned_source_profiles":
        print("Runtime reaction not aligned with learned config yet; forcing entry reload...")
        client.call_service("homeassistant", "reload_config_entry", {"entry_id": entry_id})
        runtime_diag = _wait_runtime_reaction_loaded(
            client,
            entry_id,
            reaction_id=reaction_id,
            timeout_s=args.timeout_s,
            poll_s=args.poll_s,
        )
    print("Runtime reaction diagnostics before vacation:")
    print(runtime_diag)

    _set_person_override(client, person_override_entity, "force_away")
    client.call_service("heima", "set_mode", {"mode": "vacation", "state": True})
    client.call_service("heima", "command", {"command": "recompute_now"})
    client.wait_state("sensor.heima_house_state", "vacation", args.timeout_s, args.poll_s)

    diag = _wait_reaction_ready(
        client,
        entry_id,
        reaction_id=reaction_id,
        timeout_s=args.timeout_s,
        poll_s=args.poll_s,
    )
    print("Reaction diagnostics:")
    print(diag)

    _assert(diag.get("source_profile_kind") == "learned_source_profiles", "unexpected source_profile_kind")
    _assert(bool(diag.get("source_profile_ready")), "source_profile_ready is false")
    _assert(int(diag.get("source_reaction_count") or 0) >= 2, "learned source profile too small")
    blocked_reason = str(diag.get("blocked_reason") or "")
    plan_count = int(diag.get("tonight_plan_count") or 0)
    if blocked_reason == "sun_unavailable":
        print("Skipping scheduler assertion because sun context is unavailable in the lab.")
    else:
        _assert(plan_count >= 1, f"tonight plan is empty: {diag}")
        job = _wait_scheduler_job(
            client,
            entry_id,
            reaction_id=reaction_id,
            timeout_s=args.timeout_s,
            poll_s=args.poll_s,
        )
        print("Scheduler job:")
        print(job)
        _assert(str(job.get("owner") or "") == "VacationPresenceSimulationReaction", f"unexpected scheduler owner: {job}")

    print("PASS: learned security presence proposal accepted and runtime plan became active")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
