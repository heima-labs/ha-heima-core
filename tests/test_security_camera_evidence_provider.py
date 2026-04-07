from __future__ import annotations

from types import SimpleNamespace

from custom_components.heima.runtime.domains.security_camera_evidence import (
    SecurityCameraEvidenceProvider,
)
from custom_components.heima.runtime.engine import HeimaEngine
from custom_components.heima.runtime.normalization.service import InputNormalizer


class _FakeStateObj:
    def __init__(self, state: str):
        self.state = state


class _FakeStates:
    def __init__(self, values: dict[str, str] | None = None):
        self._values = dict(values or {})

    def get(self, entity_id: str):
        value = self._values.get(entity_id)
        if value is None:
            return None
        return _FakeStateObj(value)


class _FakeBus:
    def __init__(self):
        self.events: list[tuple[str, dict]] = []

    def async_fire(self, event_type, data):
        self.events.append((event_type, dict(data)))


class _FakeServices:
    def async_services(self):
        return {"notify": {}}

    async def async_call(self, domain, service, data, blocking=False):
        return None


def _fake_hass(states: dict[str, str] | None = None):
    return SimpleNamespace(states=_FakeStates(states), bus=_FakeBus(), services=_FakeServices())


def test_security_camera_evidence_provider_reports_active_and_unavailable_sources():
    hass = _fake_hass(
        {
            "binary_sensor.front_cam_person": "on",
            "binary_sensor.garage_motion": "off",
        }
    )
    provider = SecurityCameraEvidenceProvider(hass, InputNormalizer(hass))

    result = provider.compute(
        {
            "camera_evidence_sources": [
                {
                    "id": "front_door_cam",
                    "enabled": True,
                    "role": "entry",
                    "person_entity": "binary_sensor.front_cam_person",
                },
                {
                    "id": "garage_cam",
                    "enabled": True,
                    "role": "garage",
                    "vehicle_entity": "binary_sensor.garage_vehicle",
                    "motion_entity": "binary_sensor.garage_motion",
                },
            ]
        }
    )

    assert result.as_dict()["configured_source_count"] == 2
    assert [item.kind for item in result.active_evidence] == ["person"]
    assert result.active_evidence[0].source_id == "front_door_cam"
    assert result.unavailable_sources == [
        {
            "source_id": "garage_cam",
            "role": "garage",
            "kind": "vehicle",
            "entity_id": "binary_sensor.garage_vehicle",
            "reason": "entity_not_found",
        }
    ]


def test_engine_diagnostics_expose_security_camera_evidence_section():
    hass = _fake_hass(
        {
            "alarm_control_panel.home": "disarmed",
            "binary_sensor.front_cam_person": "on",
        }
    )
    engine = HeimaEngine(
        hass=hass,
        entry=SimpleNamespace(
            options={
                "security": {
                    "enabled": True,
                    "security_state_entity": "alarm_control_panel.home",
                    "camera_evidence_sources": [
                        {
                            "id": "front_door_cam",
                            "enabled": True,
                            "role": "entry",
                            "person_entity": "binary_sensor.front_cam_person",
                        }
                    ],
                }
            }
        ),
    )
    engine._build_default_state()

    engine._compute_snapshot(reason="test")
    diagnostics = engine.diagnostics()

    assert "security_camera_evidence" in diagnostics
    section = diagnostics["security_camera_evidence"]
    assert section["configured_source_count"] == 1
    assert section["active_evidence_count"] == 1
    state_attrs = engine.state.get_sensor_attributes("heima_security_state") or {}
    assert state_attrs["camera_evidence"]["active_evidence_count"] == 1
