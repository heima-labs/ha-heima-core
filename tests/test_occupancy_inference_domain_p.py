"""Tests for OccupancyDomain consumption of OccupancySignal."""

from __future__ import annotations

from types import SimpleNamespace

from custom_components.heima.runtime.domains.occupancy import OccupancyDomain
from custom_components.heima.runtime.inference import Importance, OccupancySignal


class _State:
    def __init__(self) -> None:
        self.binaries: dict[str, bool] = {}
        self.sensors: dict[str, object] = {}

    def get_binary(self, key: str) -> bool | None:
        return self.binaries.get(key)

    def set_binary(self, key: str, value: bool) -> None:
        self.binaries[key] = value

    def set_sensor(self, key: str, value: object) -> None:
        self.sensors[key] = value


class _Observation:
    state = "off"
    source_entity_id = "binary_sensor.motion"

    def as_dict(self) -> dict[str, object]:
        return {"state": self.state, "source_entity_id": self.source_entity_id}


class _Normalizer:
    def presence(self, entity_id: str) -> _Observation:
        del entity_id
        return _Observation()

    def derive(self, **kwargs) -> SimpleNamespace:
        del kwargs
        return SimpleNamespace(
            state="off",
            plugin_id=None,
            reason="ok",
            evidence={},
            as_dict=lambda: {"state": "off"},
        )


class _Events:
    def queue_event(self, event: object) -> None:
        del event


def _signal(
    *,
    room_id: str = "studio",
    predicted_occupied: bool = True,
    confidence: float = 0.7,
    importance: Importance = Importance.SUGGEST,
) -> OccupancySignal:
    return OccupancySignal(
        source_id="occupancy_inference",
        confidence=confidence,
        importance=importance,
        ttl_s=300,
        label="test",
        room_id=room_id,
        predicted_occupied=predicted_occupied,
    )


def _compute(
    options: dict, signals: list[OccupancySignal]
) -> tuple[object, _State, OccupancyDomain]:
    domain = OccupancyDomain(SimpleNamespace(), _Normalizer())  # type: ignore[arg-type]
    state = _State()
    result = domain.compute(
        options=options,
        events=_Events(),  # type: ignore[arg-type]
        mismatch_cfg={},
        schedule_recheck=lambda **kwargs: None,
        state=state,
        now="2026-05-17T20:00:00+00:00",
        signals=signals,
    )
    return result, state, domain


def test_occupancy_domain_applies_high_confidence_signal_to_sensorless_room() -> None:
    result, state, domain = _compute(
        {"rooms": [{"room_id": "studio", "occupancy_mode": "derived", "occupancy_sources": []}]},
        [_signal()],
    )

    assert result.occupied_rooms == ["studio"]
    assert state.binaries["heima_occupancy_studio"] is True
    assert domain.room_trace["studio"]["inference_signal"]["source_id"] == "occupancy_inference"


def test_occupancy_domain_applies_false_signal_to_sensorless_room() -> None:
    result, state, domain = _compute(
        {"rooms": [{"room_id": "studio", "occupancy_mode": "derived", "occupancy_sources": []}]},
        [_signal(predicted_occupied=False)],
    )

    assert result.occupied_rooms == []
    assert state.binaries["heima_occupancy_studio"] is False
    assert domain.room_trace["studio"]["effective_state"] == "off"


def test_occupancy_domain_ignores_signal_for_sensorized_room() -> None:
    result, state, domain = _compute(
        {
            "rooms": [
                {
                    "room_id": "studio",
                    "occupancy_mode": "derived",
                    "occupancy_sources": ["binary_sensor.motion"],
                }
            ]
        },
        [_signal()],
    )

    assert result.occupied_rooms == []
    assert result.sensorized_room_count == 1
    assert state.binaries["heima_occupancy_studio"] is False
    assert "inference_signal" not in domain.room_trace["studio"]


def test_occupancy_domain_ignores_signal_for_none_mode_room() -> None:
    result, state, domain = _compute(
        {"rooms": [{"room_id": "studio", "occupancy_mode": "none", "occupancy_sources": []}]},
        [_signal()],
    )

    assert result.occupied_rooms == []
    assert state.binaries["heima_occupancy_studio"] is False
    assert "inference_signal" not in domain.room_trace["studio"]


def test_occupancy_domain_ignores_low_confidence_signal() -> None:
    result, state, domain = _compute(
        {"rooms": [{"room_id": "studio", "occupancy_mode": "derived", "occupancy_sources": []}]},
        [_signal(confidence=0.69)],
    )

    assert result.occupied_rooms == []
    assert state.binaries["heima_occupancy_studio"] is False
    assert "inference_signal" not in domain.room_trace["studio"]


def test_occupancy_domain_ignores_observe_signal() -> None:
    result, state, domain = _compute(
        {"rooms": [{"room_id": "studio", "occupancy_mode": "derived", "occupancy_sources": []}]},
        [_signal(importance=Importance.OBSERVE)],
    )

    assert result.occupied_rooms == []
    assert state.binaries["heima_occupancy_studio"] is False
    assert "inference_signal" not in domain.room_trace["studio"]
