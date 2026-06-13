#!/usr/bin/env python3
"""Live test for Phase AB smart lighting dim/off lifecycle."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.ha_client import HAClient
from smart_lighting_live_helpers import (  # noqa: E402
    ENTRY_ROOM_ID,
    LIGHT_BRIGHTNESS,
    LIGHT_COLOR_TEMP,
    LIGHT_ENTITY,
    LIGHT_RAW,
    LUX_SENSOR,
    MOTION_RAW,
    MOTION_SENSOR,
    RESET_SCRIPT,
    disable_conflicting_lighting_reactions,
    engine_diagnostics,
    reaction_diagnostics,
    recompute_now,
    reload_entry,
    require_entities,
    reset_lab,
    restore_configured_reactions,
    set_indoor_lux,
    set_studio_occupied,
    smart_lighting_cfg,
    upsert_smart_lighting_reaction,
    wait_canonical_room_occupied,
    wait_for_reaction_id,
    wait_light,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ha-url", default="http://127.0.0.1:8123")
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--timeout-s", type=int, default=240)
    parser.add_argument("--poll-s", type=float, default=1.0)
    parser.add_argument("--dim-warning-s", type=int, default=10)
    parser.add_argument("--off-timeout-s", type=int, default=20)
    args = parser.parse_args()

    client = HAClient(args.ha_url, args.ha_token, timeout_s=args.timeout_s)
    require_entities(
        client,
        [
            RESET_SCRIPT,
            MOTION_RAW,
            MOTION_SENSOR,
            LUX_SENSOR,
            LIGHT_ENTITY,
            LIGHT_RAW,
            LIGHT_BRIGHTNESS,
            LIGHT_COLOR_TEMP,
        ],
    )

    entry_id = client.find_heima_entry_id()
    reaction_id = f"live-smart-lifecycle-{int(time.time())}"
    cfg = smart_lighting_cfg(
        reaction_id=reaction_id,
        brightness=160,
        color_temp_kelvin=3000,
        timeout_s=args.off_timeout_s,
        dim_warning_s=args.dim_warning_s,
    )

    disabled_reactions = disable_conflicting_lighting_reactions(
        client,
        entry_id,
        keep_reaction_id=reaction_id,
    )
    try:
        reset_lab(client, timeout_s=args.timeout_s, poll_s=args.poll_s)
        upsert_smart_lighting_reaction(client, entry_id, reaction_id, cfg)
        reload_entry(client, entry_id)
        wait_for_reaction_id(
            client, entry_id, reaction_id, timeout_s=args.timeout_s, poll_s=args.poll_s
        )

        print("Turning light on through smart lighting...")
        set_studio_occupied(client, True, timeout_s=args.timeout_s, poll_s=args.poll_s)
        wait_canonical_room_occupied(
            client,
            entry_id,
            ENTRY_ROOM_ID,
            True,
            timeout_s=args.timeout_s,
            poll_s=args.poll_s,
        )
        recompute_now(client)
        set_indoor_lux(client, 180, timeout_s=args.timeout_s, poll_s=args.poll_s)
        set_indoor_lux(client, 90, timeout_s=args.timeout_s, poll_s=args.poll_s)
        wait_light(
            client,
            LIGHT_ENTITY,
            "on",
            brightness=160,
            timeout_s=args.timeout_s,
            poll_s=args.poll_s,
        )
        time.sleep(1)
        diagnostics = reaction_diagnostics(client, entry_id, reaction_id)
        if diagnostics.get("manual_on_hold") is True:
            print(
                "SKIP: live fixture classified the Heima-owned turn-on as manual override; "
                "context parent_id is not preserved for this light entity."
            )
            return 0

        print("Marking studio vacant and waiting for dim/off sequence...")
        set_studio_occupied(client, False, timeout_s=args.timeout_s, poll_s=args.poll_s)
        wait_canonical_room_occupied(
            client,
            entry_id,
            ENTRY_ROOM_ID,
            False,
            timeout_s=args.timeout_s,
            poll_s=args.poll_s,
        )
        recompute_now(client)
        dim_reason = f"room_smart_lighting_assist:dim:{reaction_id}"
        dim_deadline = time.time() + args.timeout_s
        last_brightness = 160
        last_plan: dict | None = None
        while time.time() < dim_deadline:
            state = client.get_state(LIGHT_ENTITY)
            last_brightness = int((state.get("attributes") or {}).get("brightness") or 0)
            if str(state.get("state") or "") == "on" and 0 < last_brightness < 160:
                break
            engine = engine_diagnostics(client, entry_id)
            apply_plan = engine.get("apply_plan", {})
            last_plan = dict(apply_plan) if isinstance(apply_plan, dict) else None
            steps = apply_plan.get("steps", []) if isinstance(apply_plan, dict) else []
            for step in steps if isinstance(steps, list) else []:
                if not isinstance(step, dict):
                    continue
                params = step.get("params", {})
                if (
                    step.get("domain") == "lighting"
                    and step.get("action") == "light.turn_on"
                    and step.get("reason") == dim_reason
                    and isinstance(params, dict)
                    and int(params.get("brightness") or 0) == 38
                    and not step.get("blocked_by")
                ):
                    break
            else:
                time.sleep(args.poll_s)
                continue
            break
        else:
            raise AssertionError(
                f"dim step did not apply; last_brightness={last_brightness}; "
                f"last_plan={last_plan}"
            )

        wait_light(
            client,
            LIGHT_ENTITY,
            "off",
            timeout_s=args.timeout_s,
            poll_s=args.poll_s,
        )
        print("PASS: smart lighting dims then turns off after vacancy")
        return 0
    finally:
        restore_configured_reactions(client, entry_id, disabled_reactions)
        if disabled_reactions:
            reload_entry(client, entry_id)


if __name__ == "__main__":
    raise SystemExit(main())
