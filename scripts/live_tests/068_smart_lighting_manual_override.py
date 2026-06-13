#!/usr/bin/env python3
"""Live test for Phase AB smart lighting external manual override handling."""

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
    RESET_SCRIPT,
    assert_true,
    manual_light_on,
    reload_entry,
    require_entities,
    reset_lab,
    set_indoor_lux,
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
    reaction_id = f"live-smart-override-{int(time.time())}"
    cfg = smart_lighting_cfg(reaction_id=reaction_id, brightness=144, color_temp_kelvin=2900)

    reset_lab(client, timeout_s=args.timeout_s, poll_s=args.poll_s)
    upsert_smart_lighting_reaction(client, entry_id, reaction_id, cfg)
    reload_entry(client, entry_id)
    wait_for_reaction_id(
        client, entry_id, reaction_id, timeout_s=args.timeout_s, poll_s=args.poll_s
    )

    print("Creating external manual ON before smart lighting can act...")
    set_studio_occupied(client, True, timeout_s=args.timeout_s, poll_s=args.poll_s)
    set_indoor_lux(client, 180, timeout_s=args.timeout_s, poll_s=args.poll_s)
    manual_light_on(client, brightness=222, color_temp_kelvin=4100)
    wait_light(
        client,
        LIGHT_ENTITY,
        "on",
        brightness=222,
        timeout_s=args.timeout_s,
        poll_s=args.poll_s,
    )
    time.sleep(2)

    print("Triggering smart-lighting lux event while manual hold should be active...")
    set_indoor_lux(client, 90, timeout_s=args.timeout_s, poll_s=args.poll_s)
    time.sleep(4)
    state = client.get_state(LIGHT_ENTITY)
    brightness = int((state.get("attributes") or {}).get("brightness") or 0)
    assert_true(
        brightness == 222,
        f"smart lighting overrode external manual brightness; expected 222 got {brightness}: {state}",
    )

    print("PASS: external manual light change holds smart lighting back")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
