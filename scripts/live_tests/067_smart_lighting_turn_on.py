#!/usr/bin/env python3
"""Live test for Phase AB smart lighting turn-on and occupied outdoor-lux gating."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.ha_client import HAClient
from smart_lighting_live_helpers import (  # noqa: E402
    LIGHT_BRIGHTNESS,
    LIGHT_COLOR_TEMP,
    LIGHT_ENTITY,
    LIGHT_RAW,
    LUX_SENSOR,
    MOTION_RAW,
    MOTION_SENSOR,
    OUTDOOR_LUX_INPUT,
    RESET_SCRIPT,
    assert_true,
    disable_conflicting_lighting_reactions,
    reload_entry,
    require_entities,
    reset_lab,
    restore_configured_reactions,
    set_indoor_lux,
    set_outdoor_lux_if_available,
    set_studio_occupied,
    smart_lighting_cfg,
    upsert_smart_lighting_reaction,
    wait_for_reaction_id,
    wait_light,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ha-url", default="http://127.0.0.1:8123")
    parser.add_argument("--ha-token", required=True)
    parser.add_argument("--timeout-s", type=int, default=90)
    parser.add_argument("--poll-s", type=float, default=1.0)
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
    reaction_id = f"live-smart-turn-on-{int(time.time())}"
    outdoor_signal = "outdoor_lux" if client.entity_exists(OUTDOOR_LUX_INPUT) else None
    cfg = smart_lighting_cfg(
        reaction_id=reaction_id,
        brightness=144,
        color_temp_kelvin=None,
        outdoor_lux_signal=outdoor_signal,
    )
    cfg["suppress_on_states"] = []

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

        print("Verifying outdoor lux trigger is ignored while studio is vacant...")
        set_studio_occupied(client, False, timeout_s=args.timeout_s, poll_s=args.poll_s)
        set_indoor_lux(client, 90, timeout_s=args.timeout_s, poll_s=args.poll_s)
        if outdoor_signal:
            set_outdoor_lux_if_available(
                client, 850, timeout_s=args.timeout_s, poll_s=args.poll_s
            )
            time.sleep(3)
            state = client.get_state(LIGHT_ENTITY)
            assert_true(
                str(state.get("state")) == "off",
                f"vacant outdoor trigger turned light on: {state}",
            )
        else:
            print("Outdoor lux fixture not present; skipped outdoor-vacant gate check.")

        print("Verifying occupied indoor lux trigger turns light on...")
        set_studio_occupied(client, True, timeout_s=args.timeout_s, poll_s=args.poll_s)
        set_indoor_lux(client, 180, timeout_s=args.timeout_s, poll_s=args.poll_s)
        set_indoor_lux(client, 90, timeout_s=args.timeout_s, poll_s=args.poll_s)
        state = wait_light(
            client,
            LIGHT_ENTITY,
            "on",
            brightness=144,
            timeout_s=args.timeout_s,
            poll_s=args.poll_s,
        )
        print(f"Light state after smart turn-on: {state}")
        print("PASS: smart lighting turns on for occupied dark room and gates vacant outdoor lux")
        return 0
    finally:
        restore_configured_reactions(client, entry_id, disabled_reactions)
        if disabled_reactions:
            reload_entry(client, entry_id)


if __name__ == "__main__":
    raise SystemExit(main())
