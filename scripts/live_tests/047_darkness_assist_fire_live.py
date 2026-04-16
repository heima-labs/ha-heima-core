#!/usr/bin/env python3
"""Live E2E test: verifica che una room_darkness_lighting_assist reaction
accenda la luce quando si entra in una stanza buia.

Flusso:
  1. Trova la reaction per label o ID
  2. Pre-check: stanza vuota, lux nel bucket atteso, luce spenta, cooldown libero
  3. Inietta presenza (POST /api/states/) sul primo occupancy_source della room
  4. Aspetta che Heima rilevi occupancy e che la luce si accenda
  5. Verifica diagnostics: fire_count aumentato, last_fired_iso impostato
  6. Cleanup: ripristina presenza, spegni la luce se l'abbiamo accesa noi

Uso:
  python3 scripts/live_tests/047_darkness_assist_fire_live.py \\
      --ha-url http://192.168.178.75:8123 \\
      --ha-token <token> \\
      --label-contains "studio"

  # oppure con ID esplicito:
  python3 scripts/live_tests/047_darkness_assist_fire_live.py \\
      --ha-url http://192.168.178.75:8123 \\
      --ha-token <token> \\
      --reaction-id b26f1616-de3f-4226-a766-297e06f7ff22
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import time
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.ha_client import HAApiError, HAClient


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _safe_dict(v: Any) -> dict[str, Any]:
    return dict(v) if isinstance(v, dict) else {}


def _safe_list(v: Any) -> list[Any]:
    return list(v) if isinstance(v, list) else []


def _step(msg: str) -> None:
    print(f"  {msg}")


def _ok(msg: str) -> None:
    print(f"  [ok] {msg}")


def _fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")


# ---------------------------------------------------------------------------
# diagnostics helpers
# ---------------------------------------------------------------------------

def _load_diag(client: HAClient) -> dict[str, Any]:
    entry_id = client.find_heima_entry_id()
    raw = client.get(f"/api/diagnostics/config_entry/{entry_id}")
    return _safe_dict(raw)


def _runtime(diag: dict[str, Any]) -> dict[str, Any]:
    return _safe_dict(_safe_dict(diag.get("data")).get("runtime"))


def _entry_options(diag: dict[str, Any]) -> dict[str, Any]:
    entry = _safe_dict(_safe_dict(diag.get("data")).get("entry"))
    return _safe_dict(entry.get("options"))


def _reactions_payload(client: HAClient) -> dict[str, Any]:
    state = client.get_state("sensor.heima_reactions_active")
    return _safe_dict(_safe_dict(state.get("attributes")).get("reactions"))


def _reaction_diag(rt: dict[str, Any], reaction_id: str) -> dict[str, Any]:
    return _safe_dict(_safe_dict(rt.get("engine")).get("reactions")).get(reaction_id) or {}


def _reaction_cfg(options: dict[str, Any], reaction_id: str) -> dict[str, Any]:
    configured = _safe_dict(_safe_dict(options.get("reactions")).get("configured"))
    cfg = configured.get(reaction_id)
    return dict(cfg) if isinstance(cfg, dict) else {}


def _room_cfg(options: dict[str, Any], room_id: str) -> dict[str, Any]:
    for room in _safe_list(options.get("rooms")):
        if isinstance(room, dict) and str(room.get("room_id") or "") == room_id:
            return dict(room)
    return {}


def _bucket_state(rt: dict[str, Any]) -> dict[str, Any]:
    canonicalizer = _safe_dict(
        _safe_dict(_safe_dict(rt.get("engine")).get("behaviors")).get("event_canonicalizer")
    )
    return _safe_dict(canonicalizer.get("bucket_state"))


def _snapshot(rt: dict[str, Any]) -> dict[str, Any]:
    return _safe_dict(_safe_dict(rt.get("engine")).get("snapshot"))


def _occupancy_trace(rt: dict[str, Any], room_id: str) -> dict[str, Any]:
    occ = _safe_dict(_safe_dict(rt.get("engine")).get("occupancy"))
    return _safe_dict(_safe_dict(occ.get("room_trace")).get(room_id))


# ---------------------------------------------------------------------------
# reaction discovery
# ---------------------------------------------------------------------------

def _find_reaction_id(
    *,
    client: HAClient,
    diag: dict[str, Any],
    reaction_id_arg: str | None,
    label_contains_arg: str | None,
) -> str:
    payload = _reactions_payload(client)
    options = _entry_options(diag)
    stored_labels: dict[str, str] = _safe_dict(
        _safe_dict(options.get("reactions")).get("labels")
    )

    if reaction_id_arg:
        if reaction_id_arg not in payload:
            raise HAApiError(f"reaction_id not found: {reaction_id_arg}")
        return reaction_id_arg

    if label_contains_arg:
        needle = label_contains_arg.strip().lower()
        for rid in sorted(payload):
            label = stored_labels.get(rid, "")
            rt = _runtime(diag)
            rdiag = _reaction_diag(rt, rid)
            reaction_type = str(_safe_dict(payload.get(rid)).get("reaction_type") or "")
            if reaction_type != "room_darkness_lighting_assist":
                continue
            haystacks = [rid.lower(), label.lower(), reaction_type.lower(),
                         str(rdiag.get("room_id") or "").lower()]
            if any(needle in h for h in haystacks):
                return rid
        # fallback: any darkness-lighting-assist
        for rid in sorted(payload):
            reaction_type = str(_safe_dict(payload.get(rid)).get("reaction_type") or "")
            if reaction_type == "room_darkness_lighting_assist":
                return rid
        raise HAApiError(
            f"nessuna room_darkness_lighting_assist con label contenente {label_contains_arg!r}"
        )

    # no filter: find the only darkness-lighting-assist
    candidates = [
        rid for rid, state in payload.items()
        if str(_safe_dict(state).get("reaction_type") or "") == "room_darkness_lighting_assist"
    ]
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise HAApiError("nessuna reaction room_darkness_lighting_assist trovata")
    raise HAApiError(
        f"trovate {len(candidates)} room_darkness_lighting_assist: "
        "specifica --label-contains o --reaction-id"
    )


# ---------------------------------------------------------------------------
# occupancy source discovery
# ---------------------------------------------------------------------------

def _first_occupancy_source(room_cfg: dict[str, Any]) -> str | None:
    for key in ("occupancy_sources", "learning_sources"):
        for src in _safe_list(room_cfg.get(key)):
            entity_id = str(_safe_dict(src).get("entity_id") or src or "").strip()
            if entity_id and "." in entity_id:
                return entity_id
    return None


# ---------------------------------------------------------------------------
# bucket comparison
# ---------------------------------------------------------------------------

def _bucket_matches_lte(
    current: str,
    expected: str,
    labels: list[str],
) -> bool:
    if not current or not expected:
        return False
    if not labels:
        return current == expected
    try:
        return labels.index(current) <= labels.index(expected)
    except ValueError:
        return current == expected


# ---------------------------------------------------------------------------
# core test
# ---------------------------------------------------------------------------

def run_test(
    client: HAClient,
    *,
    reaction_id_arg: str | None,
    label_contains_arg: str | None,
    timeout_s: int,
    poll_s: float,
    force: bool,
) -> bool:
    print("\n=== pre-load diagnostics ===")
    diag = _load_diag(client)
    rt = _runtime(diag)
    options = _entry_options(diag)

    reaction_id = _find_reaction_id(
        client=client,
        diag=diag,
        reaction_id_arg=reaction_id_arg,
        label_contains_arg=label_contains_arg,
    )
    rdiag = _reaction_diag(rt, reaction_id)
    rcfg = _reaction_cfg(options, reaction_id)
    room_id = str(rdiag.get("room_id") or rcfg.get("room_id") or "").strip()
    if not room_id:
        _fail("room_id non trovato in diagnostics")
        return False

    stored_labels = _safe_dict(_safe_dict(options.get("reactions")).get("labels"))
    label = stored_labels.get(reaction_id) or f"room_darkness_lighting_assist/{room_id}"

    print(f"\nReaction: {reaction_id}")
    print(f"Label:    {label}")
    print(f"Room:     {room_id}")

    # entity_steps (list of dicts) from persisted config
    entity_steps: list[dict[str, Any]] = _safe_list(rcfg.get("entity_steps"))
    light_entities = [
        str(s.get("entity_id") or "").strip()
        for s in entity_steps
        if str(s.get("action") or "") == "on" and str(s.get("entity_id") or "").strip()
    ]
    if not light_entities:
        _fail("nessuna entity_step con action=on trovata nel config — la reaction è correttamente configurata?")
        return False
    print(f"Lights:   {', '.join(light_entities)}")

    primary_bucket = str(rdiag.get("primary_bucket") or rcfg.get("primary_bucket") or "").strip()
    match_mode = str(rdiag.get("primary_bucket_match_mode") or "eq").strip()
    bucket_labels = [str(v) for v in _safe_list(rdiag.get("primary_bucket_labels"))]
    buckets = _bucket_state(rt)
    current_lux_bucket = str(buckets.get(f"{room_id}:room_lux") or "").strip()

    print(f"\n=== pre-check ===")
    ok = True

    # 1. reaction not muted
    payload = _reactions_payload(client)
    reaction_state = _safe_dict(payload.get(reaction_id))
    if bool(reaction_state.get("muted")):
        _fail("reaction è muted")
        ok = False
    else:
        _ok("reaction non muted")

    # 2. stanza vuota
    snap = _snapshot(rt)
    occupied_rooms = [str(r) for r in _safe_list(snap.get("occupied_rooms"))]
    if room_id in occupied_rooms:
        if not force:
            _fail(f"room '{room_id}' è già occupata — interrompo (usa --force per ignorare)")
            return False
        else:
            _fail(f"room '{room_id}' è già occupata (--force: procedo comunque)")
            ok = False
    else:
        _ok(f"room '{room_id}' vuota")

    # 3. lux nel bucket atteso
    if primary_bucket:
        lux_ok = False
        if match_mode == "lte":
            lux_ok = _bucket_matches_lte(current_lux_bucket, primary_bucket, bucket_labels)
        elif match_mode == "gte":
            lux_ok = _bucket_matches_lte(primary_bucket, current_lux_bucket, bucket_labels)
        else:
            lux_ok = current_lux_bucket == primary_bucket
        if not lux_ok:
            _fail(
                f"lux bucket corrente={current_lux_bucket!r}, atteso {match_mode}={primary_bucket!r} "
                f"(labels={bucket_labels}) — impossibile testare senza il bucket giusto"
            )
            return False
        else:
            _ok(f"lux bucket={current_lux_bucket!r} soddisfa {match_mode}={primary_bucket!r}")
    else:
        _ok("primary_bucket non configurato — skip controllo lux")

    # 4. luci spente
    lights_were_on: list[str] = []
    for eid in light_entities:
        s = client.state_from_list(eid)
        if s is None:
            domain = eid.split(".")[0] if "." in eid else "light"
            local = eid.split(".")[-1].lower() if "." in eid else eid.lower()
            available = sorted(
                str(x.get("entity_id"))
                for x in client.all_states()
                if str(x.get("entity_id", "")).startswith(f"{domain}.")
            )
            # trova la più simile per token condivisi
            def _score(a: str) -> int:
                al = a.split(".")[-1].lower()
                return sum(1 for t in local.split("_") if t and t in al)
            best = sorted(available, key=_score, reverse=True)
            _fail(
                f"entity_id configurato nella reaction non trovato in /api/states\n"
                f"  Configurato:  {eid}\n"
                f"  Più simile:   {best[0] if best else '(nessuna)'}"
            )
            print(f"  Entità {domain}.* disponibili ({len(available)}):")
            for a in available:
                print(f"    {a}")
            return False
        state = str(s.get("state") or "").strip()
        if state == "on":
            lights_were_on.append(eid)
            _fail(f"{eid} è già on")
            ok = False
        else:
            _ok(f"{eid} è {state or 'unknown'}")
    if lights_were_on and not force:
        _fail("luci già accese — interrompo (usa --force per ignorare)")
        return False

    # 5. cooldown libero
    last_fired_iso = rdiag.get("last_fired_iso")
    if last_fired_iso:
        _fail(f"cooldown potenzialmente attivo: last_fired_iso={last_fired_iso}")
        if not force:
            return False
    else:
        _ok("last_fired_iso=None → cooldown libero")

    fire_count_before = int(rdiag.get("fire_count") or 0)
    suppressed_before = int(rdiag.get("suppressed_count") or 0)
    print(f"  fire_count={fire_count_before}  suppressed_count={suppressed_before}")

    if not ok and not force:
        _fail("pre-check fallito — interrompo")
        return False

    # --- find occupancy source ---
    rcfg_room = _room_cfg(options, room_id)
    sim_entity = _first_occupancy_source(rcfg_room)
    if not sim_entity:
        _fail(
            f"nessun occupancy_source trovato nella room config di '{room_id}'. "
            "Impossibile simulare presenza."
        )
        return False
    print(f"\n=== simulate occupancy via {sim_entity} ===")

    # save original state
    _sim_s = client.state_from_list(sim_entity)
    original_sim_state = str(_sim_s.get("state") or "off") if _sim_s else "off"
    original_light_states = {
        eid: str((client.state_from_list(eid) or {}).get("state") or "off")
        for eid in light_entities
    }
    lights_we_turned_on: list[str] = []

    try:
        # inject presence
        _step(f"POST stato=on su {sim_entity} (era {original_sim_state!r})")
        client.request("POST", f"/api/states/{sim_entity}", {"state": "on"})
        time.sleep(0.5)

        # wait for occupancy (via Heima snapshot, no HA entity lookup needed)
        print(f"\n=== attendo occupancy (timeout={timeout_s}s) ===")
        deadline = time.time() + timeout_s
        occupied = False
        while time.time() < deadline:
            diag_occ = _load_diag(client)
            rt_occ = _runtime(diag_occ)
            snap_occ = _snapshot(rt_occ)
            occupied_rooms_now = [str(r) for r in _safe_list(snap_occ.get("occupied_rooms"))]
            if room_id in occupied_rooms_now:
                occupied = True
                _ok(f"room '{room_id}' in occupied_rooms")
                break
            time.sleep(poll_s)
        if not occupied:
            _fail(f"timeout: room '{room_id}' non è entrata in occupied_rooms entro {timeout_s}s")
            return False

        # wait for ALL lights to turn on
        print(f"\n=== attendo accensione luci (timeout={timeout_s}s) ===")
        pending = list(light_entities)
        deadline = time.time() + timeout_s
        while time.time() < deadline and pending:
            still_pending = []
            for eid in pending:
                s = client.state_from_list(eid)
                if s is not None and str(s.get("state") or "") == "on":
                    _ok(f"{eid} è on")
                    lights_we_turned_on.append(eid)
                else:
                    still_pending.append(eid)
            pending = still_pending
            if pending:
                time.sleep(poll_s)

        if pending:
            _fail(f"timeout: {len(pending)}/{len(light_entities)} luci non accese entro {timeout_s}s")
            for eid in pending:
                s = client.state_from_list(eid)
                state = str(s.get("state") or "not_found") if s else "not_in_ha"
                print(f"  {eid}: state={state!r}")
            # diagnostics post-mortem
            diag2 = _load_diag(client)
            rt2 = _runtime(diag2)
            rdiag2 = _reaction_diag(rt2, reaction_id)
            snap2 = _snapshot(rt2)
            print(f"  snapshot.occupied_rooms={snap2.get('occupied_rooms')}")
            print(f"  fire_count={rdiag2.get('fire_count')}  suppressed_count={rdiag2.get('suppressed_count')}")
            print(f"  last_fired_iso={rdiag2.get('last_fired_iso')}")
            print(f"  steady_condition_active={rdiag2.get('steady_condition_active')}")
            print(f"  pending_episode={rdiag2.get('pending_episode')}")
            return False

        # verify diagnostics
        print(f"\n=== verifica diagnostics ===")
        diag3 = _load_diag(client)
        rt3 = _runtime(diag3)
        rdiag3 = _reaction_diag(rt3, reaction_id)
        fire_count_after = int(rdiag3.get("fire_count") or 0)
        last_fired_iso_after = rdiag3.get("last_fired_iso")

        if fire_count_after > fire_count_before:
            _ok(f"fire_count {fire_count_before} → {fire_count_after}")
        else:
            _fail(
                f"fire_count non aumentato ({fire_count_before} → {fire_count_after}): "
                "la luce potrebbe essersi accesa per un'altra ragione"
            )
        if last_fired_iso_after:
            _ok(f"last_fired_iso={last_fired_iso_after}")
        else:
            _fail("last_fired_iso non impostato dopo il fire")

        print(f"\n=== PASS ===")
        print(f"  reaction '{label}' ha acceso: {', '.join(lights_we_turned_on) or '(nessuna — già on)'}")
        print(f"  fire_count={fire_count_after}  last_fired_iso={last_fired_iso_after}")
        return fire_count_after > fire_count_before

    finally:
        print(f"\n=== cleanup ===")
        try:
            client.request("POST", f"/api/states/{sim_entity}", {"state": original_sim_state})
            _step(f"ripristinato {sim_entity}={original_sim_state!r}")
        except Exception as exc:  # noqa: BLE001
            _step(f"WARNING: impossibile ripristinare {sim_entity}: {exc}")
        for eid in lights_we_turned_on:
            if original_light_states.get(eid) != "on":
                try:
                    client.call_service("light", "turn_off", {"entity_id": eid})
                    _step(f"spento {eid}")
                except Exception as exc:  # noqa: BLE001
                    _step(f"WARNING: impossibile spegnere {eid}: {exc}")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Live E2E: verifica che room_darkness_lighting_assist accenda la luce"
    )
    parser.add_argument("--ha-url", default=os.environ.get("HA_URL", "http://127.0.0.1:8123"))
    parser.add_argument("--ha-token", default=os.environ.get("HA_TOKEN", ""))
    parser.add_argument("--reaction-id", default=None)
    parser.add_argument("--label-contains", default="studio")
    parser.add_argument("--timeout-s", type=int, default=30)
    parser.add_argument("--poll-s", type=float, default=1.0)
    parser.add_argument(
        "--force",
        action="store_true",
        help="procedi anche se pre-check fallisce (stanza già occupata, cooldown attivo, etc.)",
    )
    args = parser.parse_args()

    if not args.ha_token:
        print("ERROR: --ha-token richiesto (o variabile HA_TOKEN)")
        return 2

    client = HAClient(base_url=args.ha_url, token=args.ha_token)
    try:
        passed = run_test(
            client,
            reaction_id_arg=args.reaction_id,
            label_contains_arg=args.label_contains,
            timeout_s=args.timeout_s,
            poll_s=args.poll_s,
            force=args.force,
        )
    except HAApiError as exc:
        print(f"\nERROR: {exc}")
        return 1
    except KeyboardInterrupt:
        print("\ninterrotto")
        return 130

    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
