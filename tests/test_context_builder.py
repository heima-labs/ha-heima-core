"""Tests for ContextBuilder (learning system Fase 2)."""

from __future__ import annotations

from custom_components.heima.runtime.context_builder import ContextBuilder
from custom_components.heima.runtime.snapshot import DecisionSnapshot


class _FakeState:
    def __init__(self, state: str, attributes: dict | None = None) -> None:
        self.state = state
        self.attributes = attributes or {}


class _FakeStates:
    def __init__(self, states: dict) -> None:
        self._states = states

    def get(self, entity_id: str):
        return self._states.get(entity_id)


class _FakeHass:
    def __init__(self, states: dict | None = None) -> None:
        self.states = _FakeStates(states or {})


def _snapshot(
    ts: str = "2026-03-10T08:00:00+00:00",
    house_state: str = "home",
    people_count: int = 1,
    occupied_rooms: list[str] | None = None,
) -> DecisionSnapshot:
    return DecisionSnapshot(
        snapshot_id="s",
        ts=ts,
        house_state=house_state,
        anyone_home=people_count > 0,
        people_count=people_count,
        occupied_rooms=occupied_rooms or [],
        lighting_intents={},
        security_state="disarmed",
    )


def test_context_builder_time_fields():
    """weekday, minute_of_day, month derived correctly from snapshot ts."""
    hass = _FakeHass()
    builder = ContextBuilder(hass)
    # 2026-03-10 is a Tuesday (weekday=1), 08:00 local = 480 min
    ctx = builder.build(_snapshot(ts="2026-03-10T07:00:00+00:00"))
    assert ctx.month == 3
    assert 0 <= ctx.weekday <= 6
    assert 0 <= ctx.minute_of_day < 1440


def test_context_builder_house_state_and_occupancy():
    hass = _FakeHass()
    builder = ContextBuilder(hass)
    ctx = builder.build(
        _snapshot(house_state="relax", people_count=2, occupied_rooms=["living", "kitchen"])
    )
    assert ctx.house_state == "relax"
    assert ctx.occupants_count == 2
    assert set(ctx.occupied_rooms) == {"living", "kitchen"}


def test_context_builder_outdoor_lux():
    hass = _FakeHass({"sensor.lux": _FakeState("320.5")})
    builder = ContextBuilder(hass, {"outdoor_lux_entity": "sensor.lux"})
    ctx = builder.build(_snapshot())
    assert ctx.outdoor_lux == 320.5


def test_context_builder_outdoor_lux_none_when_unavailable():
    hass = _FakeHass()
    builder = ContextBuilder(hass, {"outdoor_lux_entity": "sensor.missing"})
    ctx = builder.build(_snapshot())
    assert ctx.outdoor_lux is None


def test_context_builder_outdoor_temp_from_dedicated_entity():
    hass = _FakeHass({"sensor.outdoor_temp": _FakeState("12.3")})
    builder = ContextBuilder(hass, {"outdoor_temp_entity": "sensor.outdoor_temp"})
    ctx = builder.build(_snapshot())
    assert ctx.outdoor_temp == 12.3


def test_context_builder_outdoor_temp_fallback_from_weather():
    hass = _FakeHass({"weather.home": _FakeState("cloudy", {"temperature": 8.0})})
    builder = ContextBuilder(hass, {"weather_entity": "weather.home"})
    ctx = builder.build(_snapshot())
    assert ctx.outdoor_temp == 8.0


def test_context_builder_outdoor_temp_prefers_dedicated_over_weather():
    hass = _FakeHass(
        {
            "sensor.outdoor_temp": _FakeState("15.0"),
            "weather.home": _FakeState("sunny", {"temperature": 20.0}),
        }
    )
    builder = ContextBuilder(
        hass,
        {
            "outdoor_temp_entity": "sensor.outdoor_temp",
            "weather_entity": "weather.home",
        },
    )
    ctx = builder.build(_snapshot())
    assert ctx.outdoor_temp == 15.0  # dedicated wins


def test_context_builder_weather_condition():
    hass = _FakeHass({"weather.home": _FakeState("rainy", {})})
    builder = ContextBuilder(hass, {"weather_entity": "weather.home"})
    ctx = builder.build(_snapshot())
    assert ctx.weather_condition == "rainy"


def test_context_builder_signals():
    hass = _FakeHass(
        {
            "media_player.projector": _FakeState("playing"),
            "binary_sensor.tv": _FakeState("on"),
        }
    )
    builder = ContextBuilder(
        hass,
        {
            "context_signal_entities": ["media_player.projector", "binary_sensor.tv"],
        },
    )
    ctx = builder.build(_snapshot())
    assert ctx.signals["media_player.projector"] == "playing"
    assert ctx.signals["binary_sensor.tv"] == "on"


def test_context_builder_includes_room_learning_sources():
    hass = _FakeHass(
        {
            "sensor.studio_lux": _FakeState("120"),
            "binary_sensor.studio_motion": _FakeState("on"),
        }
    )
    builder = ContextBuilder(
        hass,
        {
            "learning": {"context_signal_entities": []},
            "rooms": [
                {
                    "room_id": "studio",
                    "occupancy_sources": ["binary_sensor.studio_motion"],
                    "learning_sources": ["sensor.studio_lux"],
                }
            ],
        },
    )
    ctx = builder.build(_snapshot())
    assert ctx.signals == {"sensor.studio_lux": "120"}


def test_context_builder_signals_max_10():
    entities = [f"sensor.s{i}" for i in range(15)]
    hass = _FakeHass({e: _FakeState("on") for e in entities})
    builder = ContextBuilder(hass, {"context_signal_entities": entities})
    ctx = builder.build(_snapshot())
    assert len(ctx.signals) <= 10


def test_context_builder_update_config():
    hass = _FakeHass({"sensor.lux": _FakeState("500.0")})
    builder = ContextBuilder(hass)
    ctx_before = builder.build(_snapshot())
    assert ctx_before.outdoor_lux is None

    builder.update_config({"outdoor_lux_entity": "sensor.lux"})
    ctx_after = builder.build(_snapshot())
    assert ctx_after.outdoor_lux == 500.0


def test_context_builder_no_config_returns_none_optionals():
    hass = _FakeHass()
    builder = ContextBuilder(hass)
    ctx = builder.build(_snapshot())
    assert ctx.outdoor_lux is None
    assert ctx.outdoor_temp is None
    assert ctx.weather_condition is None
    assert ctx.signals == {}
