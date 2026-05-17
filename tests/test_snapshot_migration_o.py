"""Tests for Phase O HouseSnapshot migration and new fields."""

from __future__ import annotations

from custom_components.heima.runtime.inference import HouseSnapshot


def _snapshot() -> HouseSnapshot:
    return HouseSnapshot(
        ts="2026-04-30T10:00:00+00:00",
        weekday=3,
        minute_of_day=600,
        anyone_home=True,
        named_present=("alice",),
        room_occupancy={"kitchen": True},
        detected_activities=(),
        house_state="home",
        heating_setpoint=20.5,
        heating_current_temperature=19.5,
        lighting_scenes={"kitchen": "bright"},
        security_state="disarmed",
    )


def test_house_snapshot_from_dict_migrates_legacy_security_armed() -> None:
    raw = _snapshot().as_dict()
    raw.pop("security_state")
    raw.pop("heating_current_temperature")
    raw["security_armed"] = True

    restored = HouseSnapshot.from_dict(raw)

    assert restored is not None
    assert restored.security_state == "armed_away"
    assert restored.heating_current_temperature is None
    assert "security_armed" not in restored.as_dict()


def test_house_snapshot_from_dict_defaults_legacy_disarmed_state() -> None:
    raw = _snapshot().as_dict()
    raw.pop("security_state")
    raw["security_armed"] = False

    restored = HouseSnapshot.from_dict(raw)

    assert restored is not None
    assert restored.security_state == "disarmed"


def test_house_snapshot_round_trips_new_phase_o_fields() -> None:
    snapshot = _snapshot()

    restored = HouseSnapshot.from_dict(snapshot.as_dict())

    assert restored is not None
    assert restored == snapshot
    assert restored.as_dict()["security_state"] == "disarmed"
    assert restored.as_dict()["heating_current_temperature"] == 19.5
    assert "security_armed" not in restored.as_dict()


def test_house_snapshot_semantic_key_tracks_security_state_and_current_temperature() -> None:
    base = _snapshot()
    security_changed = HouseSnapshot.from_dict({**base.as_dict(), "security_state": "triggered"})
    temperature_changed = HouseSnapshot.from_dict(
        {**base.as_dict(), "heating_current_temperature": 18.0}
    )

    assert security_changed is not None
    assert temperature_changed is not None
    assert security_changed.semantic_key() != base.semantic_key()
    assert temperature_changed.semantic_key() != base.semantic_key()
