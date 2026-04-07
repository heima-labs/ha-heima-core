from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from custom_components.heima.runtime.domains.security_camera_evidence import (
    SecurityCameraEvidenceProvider,
)
from custom_components.heima.runtime.engine import HeimaEngine
from custom_components.heima.runtime.normalization.service import InputNormalizer


class _FakeStateObj:
    def __init__(self, state: str, *, last_changed: datetime | None = None):
        self.state = state
        self.last_changed = last_changed or datetime(2026, 4, 7, 19, 0, tzinfo=timezone.utc)
        self.last_updated = self.last_changed


class _FakeStates:
    def __init__(self, values: dict[str, str] | None = None):
        self._values = dict(values or {})

    def get(self, entity_id: str):
        value = self._values.get(entity_id)
        if value is None:
            return None
        if isinstance(value, tuple):
            state, last_changed = value
            return _FakeStateObj(state, last_changed=last_changed)
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
            "binary_sensor.front_cam_person": (
                "on",
                datetime(2026, 4, 7, 20, 10, tzinfo=timezone.utc),
            ),
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
    assert result.as_dict()["active_by_kind"] == {"person": 1}
    assert result.as_dict()["active_by_role"] == {"entry": 1}
    assert [item.kind for item in result.active_evidence] == ["person"]
    assert result.active_evidence[0].source_id == "front_door_cam"
    assert result.active_evidence[0].display_name == "front_door_cam"
    assert result.active_evidence[0].last_seen_ts == "2026-04-07T20:10:00+00:00"
    assert result.unavailable_sources == [
        {
            "source_id": "garage_cam",
            "display_name": "",
            "role": "garage",
            "kind": "vehicle",
            "entity_id": "binary_sensor.garage_vehicle",
            "reason": "entity_not_found",
        }
    ]
    configured = result.as_dict()["configured_sources"]
    assert configured[0]["status"] == "active"
    assert configured[0]["active_kinds"] == ["person"]
    assert configured[1]["status"] == "partial"
    assert configured[1]["unavailable_kinds"] == ["vehicle"]


def test_security_camera_evidence_provider_marks_fully_unavailable_source():
    hass = _fake_hass({})
    provider = SecurityCameraEvidenceProvider(hass, InputNormalizer(hass))

    result = provider.compute(
        {
            "camera_evidence_sources": [
                {
                    "id": "garage_cam",
                    "enabled": True,
                    "role": "garage",
                    "person_entity": "binary_sensor.garage_person",
                    "vehicle_entity": "binary_sensor.garage_vehicle",
                }
            ]
        }
    )

    configured = result.as_dict()["configured_sources"]
    assert configured[0]["status"] == "unavailable"
    assert sorted(configured[0]["unavailable_kinds"]) == ["person", "vehicle"]
    assert result.as_dict()["source_status_counts"] == {"unavailable": 1}


def test_security_camera_evidence_provider_emits_return_home_hint_for_entry_person():
    hass = _fake_hass(
        {
            "binary_sensor.front_cam_person": "on",
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
                    "return_home_contributor": True,
                }
            ]
        }
    )

    assert result.return_home_hint is True
    assert result.return_home_hint_reasons == [
        {
            "source_id": "front_door_cam",
            "role": "entry",
            "reason": "entry_person_detected",
            "contact_active": False,
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
    assert section["source_status_counts"] == {"active": 1}
    state_attrs = engine.state.get_sensor_attributes("heima_security_state") or {}
    assert state_attrs["camera_evidence"]["active_evidence_count"] == 1


def test_security_camera_evidence_generates_entry_breach_candidate_when_armed_away():
    hass = _fake_hass(
        {
            "alarm_control_panel.home": "armed_away",
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

    security_diag = engine.diagnostics()["security"]
    candidates = security_diag["camera_evidence_trace"]["breach_candidates"]
    assert candidates == [
        {
            "rule": "armed_away_entry_person",
            "severity": "suspicious",
            "source_id": "front_door_cam",
            "role": "entry",
            "evidence_kinds": ["person"],
            "contact_active": False,
            "reason": "entry_person_detected_while_armed_away",
        }
    ]


def test_security_camera_evidence_generates_garage_breach_candidate_with_contact():
    hass = _fake_hass(
        {
            "alarm_control_panel.home": "armed_away",
            "binary_sensor.garage_vehicle": "on",
            "binary_sensor.garage_door_contact": "on",
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
                            "id": "garage_cam",
                            "enabled": True,
                            "role": "garage",
                            "vehicle_entity": "binary_sensor.garage_vehicle",
                            "contact_entity": "binary_sensor.garage_door_contact",
                        }
                    ],
                }
            }
        ),
    )
    engine._build_default_state()

    engine._compute_snapshot(reason="test")

    security_diag = engine.diagnostics()["security"]
    candidates = security_diag["camera_evidence_trace"]["breach_candidates"]
    assert candidates == [
        {
            "rule": "armed_away_garage_open_with_presence",
            "severity": "strong",
            "source_id": "garage_cam",
            "role": "garage",
            "evidence_kinds": ["vehicle"],
            "contact_active": True,
            "reason": "garage_contact_active_with_person_or_vehicle_while_armed_away",
        }
    ]


def test_security_camera_evidence_trace_surfaces_return_home_hint_reasons():
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
                            "return_home_contributor": True,
                        }
                    ],
                }
            }
        ),
    )
    engine._build_default_state()

    engine._compute_snapshot(reason="test")

    trace = engine.diagnostics()["security"]["camera_evidence_trace"]
    assert trace["return_home_hint"] is True
    assert trace["return_home_hint_reasons"] == [
        {
            "source_id": "front_door_cam",
            "role": "entry",
            "reason": "entry_person_detected",
            "contact_active": False,
        }
    ]
