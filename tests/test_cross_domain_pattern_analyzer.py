"""Tests for CrossDomainPatternAnalyzer."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from dataclasses import replace

from custom_components.heima.runtime.analyzers.cross_domain import (
    CompositeProposalQualityPolicy,
    CompositePatternCatalogAnalyzer,
    DEFAULT_COMPOSITE_PATTERN_CATALOG,
    CrossDomainPatternAnalyzer,
    RoomCoolingPatternAnalyzer,
)
from custom_components.heima.runtime.event_store import EventContext, HeimaEvent


class _StoreStub:
    def __init__(self, events):
        self._events = list(events)

    async def async_query(self, *, event_type=None, since=None, limit=None):  # noqa: ARG002
        return [e for e in self._events if event_type is None or e.event_type == event_type]


def _ctx(*, room: str, minute: int = 480) -> EventContext:
    return EventContext(
        weekday=0,
        minute_of_day=minute,
        month=3,
        house_state="home",
        occupants_count=1,
        occupied_rooms=(room,),
        outdoor_lux=None,
        outdoor_temp=None,
        weather_condition=None,
        signals={},
    )


def _state_change(
    *,
    entity_id: str,
    room: str,
    ts: str,
    old_state: str,
    new_state: str,
    device_class: str | None = None,
) -> HeimaEvent:
    domain = entity_id.split(".", 1)[0]
    return HeimaEvent(
        ts=ts,
        event_type="state_change",
        context=_ctx(room=room),
        source="unknown",
        domain=domain,
        subject_type="entity",
        subject_id=entity_id,
        room_id=room,
        data={
            "entity_id": entity_id,
            "old_state": old_state,
            "new_state": new_state,
            "unit_of_measurement": "%",
            "device_class": device_class,
        },
    )


def _lighting_event(
    *,
    entity_id: str,
    room: str,
    ts: str,
    action: str = "on",
    brightness: int | None = 128,
    color_temp_kelvin: int | None = 3000,
    rgb_color: list[int] | None = None,
) -> HeimaEvent:
    return HeimaEvent(
        ts=ts,
        event_type="lighting",
        context=_ctx(room=room),
        source="user",
        domain="light",
        subject_type="entity",
        subject_id=entity_id,
        room_id=room,
        data={
            "entity_id": entity_id,
            "room_id": room,
            "action": action,
            "brightness": brightness,
            "color_temp_kelvin": color_temp_kelvin,
            "rgb_color": rgb_color,
        },
    )


async def test_cross_domain_analyzer_requires_min_confirmed_episodes():
    analyzer = CrossDomainPatternAnalyzer()
    base = datetime(2026, 3, 1, 8, 0, tzinfo=UTC)
    events = []
    for i in range(4):
        ts = (base + timedelta(days=i * 7)).isoformat()
        fan_ts = (base + timedelta(days=i * 7, minutes=5)).isoformat()
        events.append(
            _state_change(
                entity_id="sensor.bathroom_humidity",
                room="bathroom",
                ts=ts,
                old_state="55",
                new_state="64",
                device_class="humidity",
            )
        )
        events.append(
            _state_change(
                entity_id="fan.bathroom_fan",
                room="bathroom",
                ts=fan_ts,
                old_state="off",
                new_state="on",
            )
        )
    proposals = await analyzer.analyze(_StoreStub(events))  # type: ignore[arg-type]
    assert proposals == []


async def test_cross_domain_analyzer_emits_room_signal_assist_proposal():
    analyzer = CrossDomainPatternAnalyzer()
    base = datetime(2026, 3, 1, 8, 0, tzinfo=UTC)
    events = []
    for i in range(5):
        ts = (base + timedelta(days=i * 7)).isoformat()
        temp_ts = (base + timedelta(days=i * 7, minutes=3)).isoformat()
        fan_ts = (base + timedelta(days=i * 7, minutes=5)).isoformat()
        events.extend(
            [
                _state_change(
                    entity_id="sensor.bathroom_humidity",
                    room="bathroom",
                    ts=ts,
                    old_state="55",
                    new_state="66",
                    device_class="humidity",
                ),
                _state_change(
                    entity_id="sensor.bathroom_temperature",
                    room="bathroom",
                    ts=temp_ts,
                    old_state="21.0",
                    new_state="22.1",
                    device_class="temperature",
                ),
                _state_change(
                    entity_id="fan.bathroom_fan",
                    room="bathroom",
                    ts=fan_ts,
                    old_state="off",
                    new_state="on",
                ),
            ]
        )

    proposals = await analyzer.analyze(_StoreStub(events))  # type: ignore[arg-type]
    assert len(proposals) == 1
    proposal = proposals[0]
    assert proposal.reaction_type == "room_signal_assist"
    assert proposal.description.startswith("bathroom: humidity assist")
    assert proposal.suggested_reaction_config["reaction_class"] == "RoomSignalAssistReaction"
    assert proposal.suggested_reaction_config["room_id"] == "bathroom"
    assert proposal.suggested_reaction_config["trigger_signal_entities"] == ["sensor.bathroom_humidity"]
    assert proposal.suggested_reaction_config["primary_signal_entities"] == [
        "sensor.bathroom_humidity"
    ]
    assert proposal.suggested_reaction_config["primary_signal_name"] == "humidity"
    assert proposal.suggested_reaction_config["primary_threshold_mode"] == "rise"
    assert proposal.suggested_reaction_config["primary_threshold"] == 8.0
    assert proposal.suggested_reaction_config["temperature_signal_entities"] == [
        "sensor.bathroom_temperature"
    ]
    assert proposal.suggested_reaction_config["corroboration_signal_entities"] == [
        "sensor.bathroom_temperature"
    ]
    assert proposal.suggested_reaction_config["corroboration_signal_name"] == "temperature"
    assert proposal.suggested_reaction_config["corroboration_threshold_mode"] == "rise"
    assert proposal.suggested_reaction_config["corroboration_threshold"] == 0.8
    assert proposal.suggested_reaction_config["observed_followup_entities"] == [
        "fan.bathroom_fan"
    ]
    assert proposal.suggested_reaction_config["episodes_observed"] >= 5
    diagnostics = proposal.suggested_reaction_config["learning_diagnostics"]
    assert diagnostics["pattern_id"] == "room_signal_assist"
    assert diagnostics["analyzer_id"] == "CrossDomainPatternAnalyzer"
    assert diagnostics["reaction_type"] == "room_signal_assist"
    assert diagnostics["plugin_family"] == "composite_room_assist"
    assert diagnostics["primary_signal"] == "humidity"
    assert diagnostics["corroboration_signals"] == ["temperature"]
    assert diagnostics["followup_signal"] == "ventilation"
    assert diagnostics["episodes_detected"] >= 5
    assert diagnostics["episodes_confirmed"] >= 5
    assert diagnostics["weeks_observed"] >= 2
    assert diagnostics["matched_primary_entities"] == ["sensor.bathroom_humidity"]
    assert diagnostics["matched_corroboration_entities"] == ["sensor.bathroom_temperature"]
    assert diagnostics["observed_followup_entities"] == ["fan.bathroom_fan"]
    assert proposal.confidence < 0.9


async def test_room_cooling_pattern_analyzer_emits_room_cooling_assist_proposal():
    analyzer = RoomCoolingPatternAnalyzer()
    base = datetime(2026, 3, 1, 15, 0, tzinfo=UTC)
    events = []
    for i in range(5):
        ts = (base + timedelta(days=i * 7)).isoformat()
        humidity_ts = (base + timedelta(days=i * 7, minutes=2)).isoformat()
        fan_ts = (base + timedelta(days=i * 7, minutes=5)).isoformat()
        events.extend(
            [
                _state_change(
                    entity_id="sensor.studio_temperature",
                    room="studio",
                    ts=ts,
                    old_state="24.0",
                    new_state="25.8",
                    device_class="temperature",
                ),
                _state_change(
                    entity_id="sensor.studio_humidity",
                    room="studio",
                    ts=humidity_ts,
                    old_state="52",
                    new_state="58",
                    device_class="humidity",
                ),
                _state_change(
                    entity_id="fan.studio_fan",
                    room="studio",
                    ts=fan_ts,
                    old_state="off",
                    new_state="on",
                ),
            ]
        )

    proposals = await analyzer.analyze(_StoreStub(events))  # type: ignore[arg-type]
    assert len(proposals) == 1
    proposal = proposals[0]
    assert proposal.reaction_type == "room_cooling_assist"
    assert proposal.description.startswith("studio: cooling assist")
    assert proposal.suggested_reaction_config["reaction_class"] == "RoomSignalAssistReaction"
    assert proposal.suggested_reaction_config["room_id"] == "studio"
    assert proposal.suggested_reaction_config["primary_signal_entities"] == [
        "sensor.studio_temperature"
    ]
    assert proposal.suggested_reaction_config["corroboration_signal_entities"] == [
        "sensor.studio_humidity"
    ]
    assert proposal.suggested_reaction_config["observed_followup_entities"] == [
        "fan.studio_fan"
    ]
    diagnostics = proposal.suggested_reaction_config["learning_diagnostics"]
    assert diagnostics["pattern_id"] == "room_cooling_assist"
    assert diagnostics["analyzer_id"] == "RoomCoolingPatternAnalyzer"
    assert diagnostics["reaction_type"] == "room_cooling_assist"
    assert diagnostics["plugin_family"] == "composite_room_assist"
    assert diagnostics["primary_signal"] == "temperature"
    assert diagnostics["corroboration_signals"] == ["humidity"]
    assert diagnostics["followup_signal"] == "cooling"
    assert diagnostics["matched_primary_entities"] == ["sensor.studio_temperature"]
    assert diagnostics["matched_corroboration_entities"] == ["sensor.studio_humidity"]
    assert diagnostics["observed_followup_entities"] == ["fan.studio_fan"]


async def test_catalog_analyzer_emits_room_air_quality_assist_proposal():
    analyzer = CompositePatternCatalogAnalyzer()
    base = datetime(2026, 3, 1, 10, 0, tzinfo=UTC)
    events = []
    for i in range(5):
        co2_ts = (base + timedelta(days=i * 7)).isoformat()
        fan_ts = (base + timedelta(days=i * 7, minutes=4)).isoformat()
        events.extend(
            [
                _state_change(
                    entity_id="sensor.office_co2",
                    room="office",
                    ts=co2_ts,
                    old_state="700",
                    new_state="940",
                    device_class="carbon_dioxide",
                ),
                _state_change(
                    entity_id="fan.office_ventilation",
                    room="office",
                    ts=fan_ts,
                    old_state="off",
                    new_state="on",
                ),
            ]
        )

    proposals = await analyzer.analyze(_StoreStub(events))  # type: ignore[arg-type]
    air_quality = [p for p in proposals if p.reaction_type == "room_air_quality_assist"]
    assert len(air_quality) == 1
    proposal = air_quality[0]
    assert proposal.description.startswith("office: air quality assist")
    assert proposal.suggested_reaction_config["reaction_class"] == "RoomSignalAssistReaction"
    assert proposal.suggested_reaction_config["room_id"] == "office"
    assert proposal.suggested_reaction_config["primary_signal_entities"] == ["sensor.office_co2"]
    assert proposal.suggested_reaction_config["primary_signal_name"] == "co2"
    assert proposal.suggested_reaction_config["observed_followup_entities"] == [
        "fan.office_ventilation"
    ]
    diagnostics = proposal.suggested_reaction_config["learning_diagnostics"]
    assert diagnostics["pattern_id"] == "room_air_quality_assist"
    assert diagnostics["primary_signal"] == "co2"
    assert diagnostics.get("corroboration_signals", []) == []
    assert diagnostics["followup_signal"] == "ventilation"
    assert diagnostics["matched_primary_entities"] == ["sensor.office_co2"]
    assert diagnostics["observed_followup_entities"] == ["fan.office_ventilation"]


async def test_catalog_analyzer_emits_room_darkness_lighting_assist_proposal():
    analyzer = CompositePatternCatalogAnalyzer()
    base = datetime(2026, 3, 1, 18, 0, tzinfo=UTC)
    events = []
    for i in range(5):
        lux_ts = (base + timedelta(days=i * 7)).isoformat()
        light_ts = (base + timedelta(days=i * 7, minutes=2)).isoformat()
        events.extend(
            [
                _state_change(
                    entity_id="sensor.living_room_lux",
                    room="living",
                    ts=lux_ts,
                    old_state="180",
                    new_state="95",
                    device_class="illuminance",
                ),
                _lighting_event(
                    entity_id="light.living_main",
                    room="living",
                    ts=light_ts,
                    action="on",
                    brightness=144,
                    color_temp_kelvin=2900,
                ),
            ]
        )

    proposals = await analyzer.analyze(_StoreStub(events))  # type: ignore[arg-type]
    darkness = [p for p in proposals if p.reaction_type == "room_darkness_lighting_assist"]
    assert len(darkness) == 1
    proposal = darkness[0]
    assert proposal.description.startswith("living: darkness lighting assist")
    assert proposal.suggested_reaction_config["reaction_class"] == "RoomLightingAssistReaction"
    assert proposal.suggested_reaction_config["room_id"] == "living"
    assert proposal.suggested_reaction_config["primary_signal_entities"] == [
        "sensor.living_room_lux"
    ]
    assert proposal.suggested_reaction_config["primary_threshold_mode"] == "below"
    assert proposal.suggested_reaction_config["entity_steps"] == [
        {
            "entity_id": "light.living_main",
            "action": "on",
            "brightness": 144,
            "color_temp_kelvin": 2900,
            "rgb_color": None,
        }
    ]
    diagnostics = proposal.suggested_reaction_config["learning_diagnostics"]
    assert diagnostics["pattern_id"] == "room_darkness_lighting_assist"
    assert diagnostics["primary_signal"] == "room_lux"
    assert diagnostics["followup_signal"] == "lighting_replay"


async def test_cross_domain_analyzer_filters_sparse_followup_entities_by_ratio():
    analyzer = CrossDomainPatternAnalyzer()
    base = datetime(2026, 3, 1, 8, 0, tzinfo=UTC)
    events = []
    for i in range(5):
        ts = (base + timedelta(days=i * 7)).isoformat()
        temp_ts = (base + timedelta(days=i * 7, minutes=3)).isoformat()
        fan_ts = (base + timedelta(days=i * 7, minutes=5)).isoformat()
        events.extend(
            [
                _state_change(
                    entity_id="sensor.bathroom_humidity",
                    room="bathroom",
                    ts=ts,
                    old_state="55",
                    new_state="66",
                    device_class="humidity",
                ),
                _state_change(
                    entity_id="sensor.bathroom_temperature",
                    room="bathroom",
                    ts=temp_ts,
                    old_state="21.0",
                    new_state="22.1",
                    device_class="temperature",
                ),
                _state_change(
                    entity_id="fan.bathroom_fan",
                    room="bathroom",
                    ts=fan_ts,
                    old_state="off",
                    new_state="on",
                ),
            ]
        )
        if i == 0:
            events.append(
                _state_change(
                    entity_id="switch.bathroom_aux",
                    room="bathroom",
                    ts=(base + timedelta(days=i * 7, minutes=7)).isoformat(),
                    old_state="off",
                    new_state="on",
                )
            )

    proposals = await analyzer.analyze(_StoreStub(events))  # type: ignore[arg-type]
    proposal = proposals[0]
    assert proposal.suggested_reaction_config["observed_followup_entities"] == [
        "fan.bathroom_fan"
    ]
    diagnostics = proposal.suggested_reaction_config["learning_diagnostics"]
    assert diagnostics["followup_entity_min_ratio"] == 0.5
    assert diagnostics["followup_entity_min_episodes"] == 3


async def test_cross_domain_analyzer_confidence_grows_with_more_confirmed_weeks():
    analyzer = CrossDomainPatternAnalyzer()
    base = datetime(2026, 3, 1, 8, 0, tzinfo=UTC)

    def _episode_triplet(week_index: int) -> list[HeimaEvent]:
        ts = (base + timedelta(days=week_index * 7)).isoformat()
        temp_ts = (base + timedelta(days=week_index * 7, minutes=3)).isoformat()
        fan_ts = (base + timedelta(days=week_index * 7, minutes=5)).isoformat()
        return [
            _state_change(
                entity_id="sensor.bathroom_humidity",
                room="bathroom",
                ts=ts,
                old_state="55",
                new_state="66",
                device_class="humidity",
            ),
            _state_change(
                entity_id="sensor.bathroom_temperature",
                room="bathroom",
                ts=temp_ts,
                old_state="21.0",
                new_state="22.1",
                device_class="temperature",
            ),
            _state_change(
                entity_id="fan.bathroom_fan",
                room="bathroom",
                ts=fan_ts,
                old_state="off",
                new_state="on",
            ),
        ]

    weaker_events: list[HeimaEvent] = []
    for i in range(5):
        weaker_events.extend(_episode_triplet(i))

    stronger_events = list(weaker_events)
    for i in range(5, 8):
        stronger_events.extend(_episode_triplet(i))

    weaker = (await analyzer.analyze(_StoreStub(weaker_events)))[0]  # type: ignore[arg-type]
    stronger = (await analyzer.analyze(_StoreStub(stronger_events)))[0]  # type: ignore[arg-type]

    assert weaker.confidence < stronger.confidence
    assert stronger.confidence <= 0.95


async def test_room_cooling_pattern_analyzer_can_override_quality_policy():
    analyzer = RoomCoolingPatternAnalyzer(
        quality_policy=CompositeProposalQualityPolicy(
            followup_entity_min_ratio=0.8,
            followup_entity_min_episodes=4,
            corroboration_promote_min_ratio=0.8,
            corroboration_promote_min_episodes=4,
        )
    )
    base = datetime(2026, 3, 1, 15, 0, tzinfo=UTC)
    events = []
    for i in range(5):
        ts = (base + timedelta(days=i * 7)).isoformat()
        fan_ts = (base + timedelta(days=i * 7, minutes=5)).isoformat()
        events.extend(
            [
                _state_change(
                    entity_id="sensor.studio_temperature",
                    room="studio",
                    ts=ts,
                    old_state="24.0",
                    new_state="25.8",
                    device_class="temperature",
                ),
                _state_change(
                    entity_id="fan.studio_fan",
                    room="studio",
                    ts=fan_ts,
                    old_state="off",
                    new_state="on",
                ),
            ]
        )
        if i < 3:
            events.append(
                _state_change(
                    entity_id="sensor.studio_humidity",
                    room="studio",
                    ts=(base + timedelta(days=i * 7, minutes=2)).isoformat(),
                    old_state="52",
                    new_state="58",
                    device_class="humidity",
                )
            )

    proposals = await analyzer.analyze(_StoreStub(events))  # type: ignore[arg-type]
    proposal = proposals[0]
    assert proposal.suggested_reaction_config["corroboration_signal_entities"] == []
    diagnostics = proposal.suggested_reaction_config["learning_diagnostics"]
    assert diagnostics["corroboration_promote_min_ratio"] == 0.8
    assert diagnostics["corroboration_promote_min_episodes"] == 4
    assert diagnostics["matched_primary_entities"] == ["sensor.studio_temperature"]
    assert diagnostics["observed_followup_entities"] == ["fan.studio_fan"]


async def test_catalog_analyzer_keeps_only_dominant_candidate_per_logical_slot():
    duplicate_signal_pattern = replace(
        DEFAULT_COMPOSITE_PATTERN_CATALOG[0],
        pattern_id="room_signal_assist_duplicate",
        analyzer_id="CompositePatternCatalogAnalyzer",
        fingerprint_key="humidity_burst_duplicate",
        confidence_builder=lambda confirmed: 0.6,
        description_builder=lambda room_id, observed, corroborated: (
            f"{room_id}: humidity assist duplicate ({observed}/{corroborated})"
        ),
    )
    analyzer = CompositePatternCatalogAnalyzer(
        catalog=(
            DEFAULT_COMPOSITE_PATTERN_CATALOG[0],
            duplicate_signal_pattern,
        )
    )
    base = datetime(2026, 3, 1, 8, 0, tzinfo=UTC)
    events = []
    for i in range(5):
        ts = (base + timedelta(days=i * 7)).isoformat()
        temp_ts = (base + timedelta(days=i * 7, minutes=3)).isoformat()
        fan_ts = (base + timedelta(days=i * 7, minutes=5)).isoformat()
        events.extend(
            [
                _state_change(
                    entity_id="sensor.bathroom_humidity",
                    room="bathroom",
                    ts=ts,
                    old_state="55",
                    new_state="66",
                    device_class="humidity",
                ),
                _state_change(
                    entity_id="sensor.bathroom_temperature",
                    room="bathroom",
                    ts=temp_ts,
                    old_state="21.0",
                    new_state="22.1",
                    device_class="temperature",
                ),
                _state_change(
                    entity_id="fan.bathroom_fan",
                    room="bathroom",
                    ts=fan_ts,
                    old_state="off",
                    new_state="on",
                ),
            ]
        )

    proposals = await analyzer.analyze(_StoreStub(events))  # type: ignore[arg-type]

    assert len(proposals) == 1
    proposal = proposals[0]
    assert proposal.reaction_type == "room_signal_assist"
    assert proposal.confidence > 0.6
    assert "duplicate" not in proposal.description


def test_default_composite_pattern_catalog_exposes_current_v1_patterns():
    pattern_ids = {definition.pattern_id for definition in DEFAULT_COMPOSITE_PATTERN_CATALOG}
    reaction_types = {definition.reaction_type for definition in DEFAULT_COMPOSITE_PATTERN_CATALOG}

    assert pattern_ids == {
        "room_signal_assist",
        "room_cooling_assist",
        "room_air_quality_assist",
        "room_darkness_lighting_assist",
    }
    assert reaction_types == {
        "room_signal_assist",
        "room_cooling_assist",
        "room_air_quality_assist",
        "room_darkness_lighting_assist",
    }


async def test_catalog_analyzer_emits_both_current_v1_patterns():
    analyzer = CompositePatternCatalogAnalyzer()
    base_bathroom = datetime(2026, 3, 1, 8, 0, tzinfo=UTC)
    base_studio = datetime(2026, 3, 1, 15, 0, tzinfo=UTC)
    events = []
    for i in range(5):
        events.extend(
            [
                _state_change(
                    entity_id="sensor.bathroom_humidity",
                    room="bathroom",
                    ts=(base_bathroom + timedelta(days=i * 7)).isoformat(),
                    old_state="55",
                    new_state="66",
                    device_class="humidity",
                ),
                _state_change(
                    entity_id="sensor.bathroom_temperature",
                    room="bathroom",
                    ts=(base_bathroom + timedelta(days=i * 7, minutes=3)).isoformat(),
                    old_state="21.0",
                    new_state="22.1",
                    device_class="temperature",
                ),
                _state_change(
                    entity_id="fan.bathroom_fan",
                    room="bathroom",
                    ts=(base_bathroom + timedelta(days=i * 7, minutes=5)).isoformat(),
                    old_state="off",
                    new_state="on",
                ),
                _state_change(
                    entity_id="sensor.studio_temperature",
                    room="studio",
                    ts=(base_studio + timedelta(days=i * 7)).isoformat(),
                    old_state="24.0",
                    new_state="25.8",
                    device_class="temperature",
                ),
                _state_change(
                    entity_id="sensor.studio_humidity",
                    room="studio",
                    ts=(base_studio + timedelta(days=i * 7, minutes=2)).isoformat(),
                    old_state="52",
                    new_state="58",
                    device_class="humidity",
                ),
                _state_change(
                    entity_id="fan.studio_fan",
                    room="studio",
                    ts=(base_studio + timedelta(days=i * 7, minutes=5)).isoformat(),
                    old_state="off",
                    new_state="on",
                ),
                _state_change(
                    entity_id="sensor.office_co2",
                    room="office",
                    ts=(base_studio + timedelta(days=i * 7, minutes=30)).isoformat(),
                    old_state="700",
                    new_state="930",
                    device_class="carbon_dioxide",
                ),
                _state_change(
                    entity_id="fan.office_ventilation",
                    room="office",
                    ts=(base_studio + timedelta(days=i * 7, minutes=34)).isoformat(),
                    old_state="off",
                    new_state="on",
                ),
                _state_change(
                    entity_id="sensor.living_room_lux",
                    room="living",
                    ts=(base_studio + timedelta(days=i * 7, minutes=40)).isoformat(),
                    old_state="180",
                    new_state="90",
                    device_class="illuminance",
                ),
                _lighting_event(
                    entity_id="light.living_main",
                    room="living",
                    ts=(base_studio + timedelta(days=i * 7, minutes=42)).isoformat(),
                    action="on",
                    brightness=144,
                    color_temp_kelvin=2900,
                ),
            ]
        )

    proposals = await analyzer.analyze(_StoreStub(events))  # type: ignore[arg-type]
    reaction_types = {proposal.reaction_type for proposal in proposals}
    assert reaction_types == {
        "room_signal_assist",
        "room_cooling_assist",
        "room_air_quality_assist",
        "room_darkness_lighting_assist",
    }
    diagnostics_by_type = {
        proposal.reaction_type: proposal.suggested_reaction_config["learning_diagnostics"]
        for proposal in proposals
    }
    assert diagnostics_by_type["room_signal_assist"]["room_id"] == "bathroom"
    assert diagnostics_by_type["room_cooling_assist"]["room_id"] == "studio"
    assert diagnostics_by_type["room_air_quality_assist"]["room_id"] == "office"
    assert diagnostics_by_type["room_darkness_lighting_assist"]["room_id"] == "living"
