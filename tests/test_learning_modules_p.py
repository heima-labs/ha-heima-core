"""Tests for Phase P learning modules."""

from __future__ import annotations

from datetime import datetime

from custom_components.heima.runtime.inference import (
    HouseSnapshot,
    Importance,
    InferenceContext,
    LightingPatternModule,
    RoomStateCorrelationModule,
)


class _FakeStore:
    def __init__(self, snapshots: list[HouseSnapshot]) -> None:
        self._snapshots = snapshots

    def snapshots(self) -> list[HouseSnapshot]:
        return list(self._snapshots)


def _context(
    *,
    minute_of_day: int = 20 * 60,
    previous_house_state: str = "relax",
    room_occupancy: dict[str, bool] | None = None,
) -> InferenceContext:
    return InferenceContext(
        now_local=datetime(2026, 5, 17, 20, 0),
        weekday=6,
        minute_of_day=minute_of_day,
        anyone_home=True,
        named_present=("alice",),
        room_occupancy=room_occupancy or {},
        previous_house_state=previous_house_state,
        previous_heating_setpoint=None,
        previous_lighting_scenes={},
        previous_activity_names=(),
    )


def _snapshot(
    *,
    minute_of_day: int = 20 * 60,
    house_state: str = "relax",
    room_occupancy: dict[str, bool] | None = None,
    lighting_scenes: dict[str, str] | None = None,
) -> HouseSnapshot:
    return HouseSnapshot(
        ts="2026-05-17T20:00:00+00:00",
        weekday=6,
        minute_of_day=minute_of_day,
        anyone_home=True,
        named_present=("alice",),
        room_occupancy=room_occupancy if room_occupancy is not None else {"living": True},
        detected_activities=(),
        house_state=house_state,
        heating_setpoint=None,
        lighting_scenes=lighting_scenes if lighting_scenes is not None else {"living": "relax"},
        security_state="disarmed",
    )


async def test_lighting_pattern_module_returns_empty_before_analyze() -> None:
    module = LightingPatternModule()

    assert module.infer(_context()) == []


async def test_lighting_pattern_module_respects_min_support() -> None:
    module = LightingPatternModule()

    await module.analyze(_FakeStore([_snapshot() for _ in range(7)]))

    assert module.infer(_context()) == []


async def test_lighting_pattern_module_emits_suggest_signal_at_threshold() -> None:
    module = LightingPatternModule()
    snapshots = [_snapshot(lighting_scenes={"living": "relax"}) for _ in range(8)]

    await module.analyze(_FakeStore(snapshots))
    signals = module.infer(_context(room_occupancy={}))

    assert len(signals) == 1
    assert signals[0].source_id == "lighting_pattern"
    assert signals[0].room_id == "living"
    assert signals[0].predicted_scene == "relax"
    assert signals[0].confidence == 1.0
    assert signals[0].importance == Importance.SUGGEST


async def test_lighting_pattern_module_uses_raw_confidence_ratio() -> None:
    module = LightingPatternModule()
    snapshots = [_snapshot(lighting_scenes={"living": "relax"}) for _ in range(7)]
    snapshots.extend(_snapshot(lighting_scenes={"living": "bright"}) for _ in range(3))

    await module.analyze(_FakeStore(snapshots))
    signals = module.infer(_context())

    assert len(signals) == 1
    assert signals[0].predicted_scene == "relax"
    assert signals[0].confidence == 0.7


async def test_lighting_pattern_module_drops_below_confidence_threshold() -> None:
    module = LightingPatternModule()
    snapshots = [_snapshot(lighting_scenes={"living": "relax"}) for _ in range(6)]
    snapshots.extend(_snapshot(lighting_scenes={"living": "bright"}) for _ in range(4))

    await module.analyze(_FakeStore(snapshots))

    assert module.infer(_context()) == []


async def test_lighting_pattern_module_uses_hour_bucket() -> None:
    module = LightingPatternModule()
    snapshots = [
        _snapshot(minute_of_day=20 * 60 + 45, lighting_scenes={"living": "relax"})
        for _ in range(8)
    ]

    await module.analyze(_FakeStore(snapshots))

    assert module.infer(_context(minute_of_day=20 * 60 + 5))
    assert module.infer(_context(minute_of_day=21 * 60)) == []


async def test_lighting_pattern_module_separates_house_state() -> None:
    module = LightingPatternModule()
    snapshots = [
        _snapshot(house_state="relax", lighting_scenes={"living": "relax"})
        for _ in range(8)
    ]
    snapshots.extend(
        _snapshot(house_state="working", lighting_scenes={"living": "focus"})
        for _ in range(8)
    )

    await module.analyze(_FakeStore(snapshots))

    assert module.infer(_context(previous_house_state="relax"))[0].predicted_scene == "relax"
    assert module.infer(_context(previous_house_state="working"))[0].predicted_scene == "focus"


async def test_lighting_pattern_module_iterates_model_rooms_not_context_occupancy() -> None:
    module = LightingPatternModule()
    snapshots = [
        _snapshot(lighting_scenes={"living": "relax", "studio": "focus"})
        for _ in range(8)
    ]

    await module.analyze(_FakeStore(snapshots))
    signals = module.infer(_context(room_occupancy={"kitchen": True}))

    assert [(signal.room_id, signal.predicted_scene) for signal in signals] == [
        ("living", "relax"),
        ("studio", "focus"),
    ]


async def test_lighting_pattern_module_ignores_empty_house_state_or_scenes() -> None:
    module = LightingPatternModule()
    snapshots = [_snapshot(house_state="", lighting_scenes={"living": "relax"}) for _ in range(8)]
    snapshots.extend(_snapshot(lighting_scenes={}) for _ in range(8))

    await module.analyze(_FakeStore(snapshots))

    assert module.infer(_context()) == []
    assert module.diagnostics()["slot_count"] == 0


async def test_lighting_pattern_module_diagnostics() -> None:
    module = LightingPatternModule()

    await module.analyze(_FakeStore([_snapshot() for _ in range(8)]))

    assert module.diagnostics() == {
        "module_id": "lighting_pattern",
        "ready": True,
        "slot_count": 1,
        "analyzed_snapshots": 8,
        "min_support": 8,
        "confidence_threshold": 0.65,
    }


async def test_room_state_correlation_returns_empty_before_analyze() -> None:
    module = RoomStateCorrelationModule()

    assert module.infer(_context(room_occupancy={"living": True})) == []


async def test_room_state_correlation_respects_min_support() -> None:
    module = RoomStateCorrelationModule()
    snapshots = [
        _snapshot(house_state="relax", room_occupancy={"living": True})
        for _ in range(14)
    ]

    await module.analyze(_FakeStore(snapshots))

    assert module.infer(_context(room_occupancy={"living": True})) == []


async def test_room_state_correlation_emits_suggest_signal_at_threshold() -> None:
    module = RoomStateCorrelationModule()
    snapshots = [
        _snapshot(house_state="relax", room_occupancy={"living": True})
        for _ in range(15)
    ]

    await module.analyze(_FakeStore(snapshots))
    signals = module.infer(_context(room_occupancy={"living": True}))

    assert len(signals) == 1
    assert signals[0].source_id == "room_state_correlation"
    assert signals[0].predicted_state == "relax"
    assert signals[0].confidence == 1.0
    assert signals[0].importance == Importance.SUGGEST


async def test_room_state_correlation_uses_raw_confidence_ratio() -> None:
    module = RoomStateCorrelationModule()
    snapshots = [
        _snapshot(house_state="working", room_occupancy={"studio": True})
        for _ in range(9)
    ]
    snapshots.extend(
        _snapshot(house_state="home", room_occupancy={"studio": True})
        for _ in range(6)
    )

    await module.analyze(_FakeStore(snapshots))
    signals = module.infer(_context(room_occupancy={"studio": True}))

    assert len(signals) == 1
    assert signals[0].predicted_state == "working"
    assert signals[0].confidence == 0.6


async def test_room_state_correlation_drops_below_confidence_threshold() -> None:
    module = RoomStateCorrelationModule()
    snapshots = [
        _snapshot(house_state="working", room_occupancy={"studio": True})
        for _ in range(8)
    ]
    snapshots.extend(
        _snapshot(house_state="home", room_occupancy={"studio": True})
        for _ in range(7)
    )

    await module.analyze(_FakeStore(snapshots))

    assert module.infer(_context(room_occupancy={"studio": True})) == []


async def test_room_state_correlation_uses_frozenset_pattern_order_insensitive() -> None:
    module = RoomStateCorrelationModule()
    snapshots = [
        _snapshot(
            house_state="working",
            room_occupancy={"studio": True, "kitchen": True, "living": False},
        )
        for _ in range(15)
    ]

    await module.analyze(_FakeStore(snapshots))
    signals = module.infer(_context(room_occupancy={"kitchen": True, "studio": True}))

    assert len(signals) == 1
    assert signals[0].predicted_state == "working"


async def test_room_state_correlation_ignores_empty_pattern() -> None:
    module = RoomStateCorrelationModule()
    snapshots = [
        _snapshot(house_state="away", room_occupancy={})
        for _ in range(15)
    ]

    await module.analyze(_FakeStore(snapshots))

    assert module.infer(_context(room_occupancy={})) == []
    assert module.diagnostics()["pattern_count"] == 0


async def test_room_state_correlation_separates_room_patterns() -> None:
    module = RoomStateCorrelationModule()
    snapshots = [
        _snapshot(house_state="working", room_occupancy={"studio": True})
        for _ in range(15)
    ]
    snapshots.extend(
        _snapshot(house_state="relax", room_occupancy={"living": True})
        for _ in range(15)
    )

    await module.analyze(_FakeStore(snapshots))

    assert module.infer(_context(room_occupancy={"studio": True}))[0].predicted_state == "working"
    assert module.infer(_context(room_occupancy={"living": True}))[0].predicted_state == "relax"


async def test_room_state_correlation_ignores_empty_house_state() -> None:
    module = RoomStateCorrelationModule()
    snapshots = [
        _snapshot(house_state="", room_occupancy={"studio": True})
        for _ in range(15)
    ]

    await module.analyze(_FakeStore(snapshots))

    assert module.infer(_context(room_occupancy={"studio": True})) == []
    assert module.diagnostics()["pattern_count"] == 0


async def test_room_state_correlation_diagnostics() -> None:
    module = RoomStateCorrelationModule()

    await module.analyze(
        _FakeStore(
            [
                _snapshot(house_state="working", room_occupancy={"studio": True})
                for _ in range(15)
            ]
        )
    )

    assert module.diagnostics() == {
        "module_id": "room_state_correlation",
        "ready": True,
        "pattern_count": 1,
        "analyzed_snapshots": 15,
        "min_support": 15,
        "confidence_threshold": 0.6,
    }
