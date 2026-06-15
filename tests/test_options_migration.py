from custom_components.heima.options_migration import migrate_learning_external_context_options


def test_migrate_learning_external_context_options_moves_legacy_sources():
    options = {
        "learning": {
            "outdoor_lux_entity": "sensor.old_lux",
            "outdoor_temp_entity": "sensor.old_temp",
            "weather_entity": "weather.home",
            "context_signal_entities": ["media_player.projector"],
        },
        "external_context": {
            "outdoor_temp": "sensor.canonical_temp",
        },
    }

    migrated, changed = migrate_learning_external_context_options(options)

    assert changed is True
    assert migrated["learning"] == {"context_signal_entities": ["media_player.projector"]}
    assert migrated["external_context"] == {
        "outdoor_lux": "sensor.old_lux",
        "outdoor_temp": "sensor.canonical_temp",
        "weather_condition": "weather.home",
    }


def test_migrate_learning_external_context_options_noops_without_legacy_sources():
    options = {
        "learning": {
            "context_signal_entities": ["media_player.projector"],
        },
        "external_context": {
            "outdoor_lux": "sensor.canonical_lux",
        },
    }

    migrated, changed = migrate_learning_external_context_options(options)

    assert changed is False
    assert migrated is options
