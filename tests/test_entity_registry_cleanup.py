from types import SimpleNamespace

import pytest

from custom_components.heima.__init__ import _async_cleanup_stale_entities
from custom_components.heima.const import OPT_PEOPLE_ANON, OPT_ROOMS, STRUCTURAL_OPTION_KEYS


class _FakeEntityRegistry:
    def __init__(self, entries):
        self.entities = {entry.entity_id: entry for entry in entries}
        self.removed: list[str] = []
        self.renamed: list[tuple[str, str]] = []

    def async_remove(self, entity_id: str) -> None:
        self.removed.append(entity_id)

    def async_update_entity(self, entity_id: str, *, new_entity_id: str) -> None:
        self.renamed.append((entity_id, new_entity_id))


@pytest.mark.asyncio
async def test_cleanup_stale_heima_entities(monkeypatch):
    entry = SimpleNamespace(
        entry_id="entry-1",
        options={
            OPT_PEOPLE_ANON: {"enabled": True},
            OPT_ROOMS: [
                {"room_id": "studio", "display_name": "Studio"},
                {"room_id": "living", "display_name": "Living"},
                {"room_id": "bathroom", "display_name": "Bathroom"},
            ],
        },
    )
    fake_registry = _FakeEntityRegistry(
        [
            SimpleNamespace(
                entity_id="binary_sensor.heima_occupancy_studio",
                unique_id="entry-1_heima_occupancy_studio",
                config_entry_id=["entry-1"],
            ),
            SimpleNamespace(
                entity_id="binary_sensor.heima_occupancy_soggiorno",
                unique_id="entry-1_heima_occupancy_soggiorno",
                config_entry_id=["entry-1"],
            ),
            SimpleNamespace(
                entity_id="sensor.heima_occupancy_bagno_source",
                unique_id="entry-1_heima_occupancy_bagno_source",
                config_entry_id=["entry-1"],
            ),
            SimpleNamespace(
                entity_id="sensor.heima_anonymous_confidence",
                unique_id="entry-1_heima_anonymous_presence_confidence",
                config_entry_id="entry-1",
            ),
            SimpleNamespace(
                entity_id="binary_sensor.unrelated",
                unique_id="other-domain-id",
                config_entry_id="entry-1",
            ),
        ]
    )
    monkeypatch.setattr(
        "custom_components.heima.__init__.er.async_get",
        lambda hass: fake_registry,
    )

    await _async_cleanup_stale_entities(SimpleNamespace(), entry)

    assert fake_registry.removed == [
        "binary_sensor.heima_occupancy_soggiorno",
        "sensor.heima_occupancy_bagno_source",
    ]
    assert fake_registry.renamed == [
        (
            "sensor.heima_anonymous_confidence",
            "sensor.heima_anonymous_presence_confidence",
        )
    ]


def test_people_anonymous_is_structural():
    assert OPT_PEOPLE_ANON in STRUCTURAL_OPTION_KEYS
