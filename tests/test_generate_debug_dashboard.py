from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "generate_debug_dashboard.py"
    spec = importlib.util.spec_from_file_location("generate_debug_dashboard", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_generate_dashboard_yaml_includes_runtime_rooms_and_actions() -> None:
    module = _load_module()
    inventory = {
        "mode": "test-lab",
        "generated_from": "http://ha.local",
        "rooms": [
            {
                "room_id": "studio",
                "display_name": "Studio",
                "area_id": "area_studio",
                "occupancy_mode": "derived",
                "entities": ["binary_sensor.heima_occupancy_studio", "light.studio_main"],
                "entity_count": 2,
                "reactions": [],
                "reaction_count": 0,
            }
        ],
        "heima_entities": [
            "binary_sensor.heima_occupancy_studio",
            "sensor.heima_house_state",
            "sensor.heima_reaction_proposals",
        ],
        "state_by_id": {
            "binary_sensor.heima_occupancy_studio": {
                "state": "on",
                "attributes": {"friendly_name": "Studio occupancy"},
            },
            "light.studio_main": {
                "state": "off",
                "attributes": {"friendly_name": "Studio main"},
            },
            "sensor.heima_house_state": {
                "state": "home",
                "attributes": {"friendly_name": "Heima house state"},
            },
            "sensor.heima_reaction_proposals": {
                "state": "0",
                "attributes": {"friendly_name": "Heima reaction proposals"},
            },
            "script.test_heima_reset": {
                "state": "off",
                "attributes": {"friendly_name": "Test Heima reset"},
            },
        },
        "common_entities": ["sensor.heima_house_state"],
        "learning_entities": ["sensor.heima_reaction_proposals"],
        "anomaly_entities": [],
        "occupancy_entities": ["binary_sensor.heima_occupancy_studio"],
        "heating_entities": [],
        "security_entities": [],
        "test_lab_entities": ["script.test_heima_reset"],
        "configured_reactions": [],
        "reaction_count": 0,
        "diagnostics_summary": {
            "snapshot": {"house_state": "home"},
            "apply_plan_steps": 0,
            "active_reactions": 0,
            "active_reaction_rows": [],
            "muted_reactions": 0,
            "learning_modules": [],
            "lighting": {},
        },
        "actions": {"heima_command": True, "test_reset": True},
    }

    yaml_text = module.generate_dashboard_yaml(inventory)

    assert "Heima Developer Debug" in yaml_text
    assert "Room: Studio" in yaml_text
    assert "binary_sensor.heima_occupancy_studio" in yaml_text
    assert "service: heima.command" in yaml_text
    assert "service: script.test_heima_reset" in yaml_text


def test_runtime_reactions_markdown_renders_compact_table() -> None:
    module = _load_module()
    inventory = {
        "configured_reactions": [],
        "diagnostics_summary": {
            "lighting": {},
            "active_reaction_rows": [
                {
                    "reaction_id": "rx-1",
                    "reaction_type": "room_smart_lighting_assist",
                    "room_id": "studio",
                    "fire_count": 2,
                    "suppressed_count": 1,
                    "state": "entity_steps",
                }
            ],
        },
    }

    cards = module.generate_reactions_section(inventory)
    rendered = "\n".join(cards)

    assert "Reazioni Runtime Attive" in rendered
    assert "room_smart_lighting_assist" in rendered
    assert "entity_steps" in rendered
