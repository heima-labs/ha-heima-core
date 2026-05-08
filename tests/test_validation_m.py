from __future__ import annotations

from types import SimpleNamespace

import pytest

from custom_components.heima.config_flow import HeimaOptionsFlowHandler
from custom_components.heima.coordinator import HeimaCoordinator
from custom_components.heima.validation import build_validation_report


class _FakeDiagnosticsSource:
    def __init__(self, payload: dict | None = None) -> None:
        self.payload = payload or {}

    def diagnostics(self) -> dict:
        return dict(self.payload)


async def _async_noop() -> None:
    return None


def _complete_options() -> dict:
    return {
        "people_named": [{"person_entity": "person.alice"}],
        "rooms": [
            {
                "room_id": "kitchen",
                "occupancy_sources": ["binary_sensor.kitchen_motion"],
            }
        ],
        "security": {
            "enabled": True,
            "security_state_entity": "alarm_control_panel.home",
        },
        "activity_bindings": {
            "stove_on": {"entity_id": "sensor.stove_power"},
            "oven_on": {"entity_id": "sensor.oven_power"},
            "tv_active": {"entity_id": "media_player.living_tv"},
            "pc_active": {"entity_id": "sensor.pc_power"},
            "shower_running": {"bathroom_humidity_entity": "sensor.bath_humidity"},
            "washing_machine_running": {"entity_id": "sensor.washer_power"},
            "dishwasher_running": {"entity_id": "sensor.dishwasher_power"},
        },
    }


def _coordinator(options: dict | None = None) -> HeimaCoordinator:
    coordinator = HeimaCoordinator.__new__(HeimaCoordinator)
    coordinator.entry = SimpleNamespace(entry_id="entry-1", options=options or {})
    coordinator.engine = SimpleNamespace(
        health=SimpleNamespace(ok=True, reason="initialized"),
        state=SimpleNamespace(
            set_sensor=lambda *_args, **_kwargs: None,
            set_sensor_attributes=lambda *_args, **_kwargs: None,
        ),
        diagnostics=lambda: {"engine": "ok"},
    )
    coordinator._event_store = _FakeDiagnosticsSource({"events": 1})
    coordinator._proposal_engine = _FakeDiagnosticsSource({"pending": 0})
    coordinator._approval_store = _FakeDiagnosticsSource({"total_records": 0})
    coordinator._house_snapshot_store = _FakeDiagnosticsSource({"total_snapshots": 0})
    coordinator._outcome_tracker = _FakeDiagnosticsSource({"outcomes": 1})
    coordinator._ha_backed_reconciliation_summary = {}
    coordinator._last_anomaly = None
    coordinator._last_invariant_violation = None
    coordinator._last_diagnostics = {}
    coordinator.async_refresh = _async_noop
    return coordinator


def test_validation_report_complete_config_is_ok() -> None:
    report = build_validation_report(
        options=_complete_options(),
        snapshot_count=12,
        approval_count=1,
        pending_proposal_count=0,
    )

    assert report.severity == "ok"
    assert report.as_dict()["warning_count"] == 0
    sections = {section.key: section for section in report.sections}
    assert "shower_running" in sections["activities"].available
    assert "security_presence_mismatch" in sections["invariants"].available
    assert "learning_history" in sections["learning"].available


def test_validation_report_missing_bindings_are_human_readable_warnings() -> None:
    report = build_validation_report(options={}, snapshot_count=0)

    assert report.severity == "warning"
    payload = report.as_dict()
    descriptions = [
        issue["description"] for section in payload["sections"] for issue in section["issues"]
    ]
    assert any("Shower detection needs" in description for description in descriptions)
    assert any(
        "stove_on needs a power or media entity binding" in description
        for description in descriptions
    )
    assert any(
        "Presence/occupancy mismatch checks need" in description for description in descriptions
    )


@pytest.mark.asyncio
async def test_coordinator_diagnostics_include_installation_validation() -> None:
    coordinator = _coordinator(_complete_options())
    coordinator._house_snapshot_store = _FakeDiagnosticsSource({"total_snapshots": 12})
    coordinator._approval_store = _FakeDiagnosticsSource({"total_records": 1})

    payload = await coordinator.async_run_diagnostics()

    validation = payload["installation_validation"]
    assert validation["severity"] == "ok"
    assert validation["summary"] == "Installation validation passed."


def test_health_attributes_include_installation_validation() -> None:
    coordinator = _coordinator({})

    attrs = coordinator._health_attributes()  # noqa: SLF001

    assert attrs["installation_validation"]["severity"] == "warning"


@pytest.mark.asyncio
async def test_options_flow_validation_step_uses_coordinator_report() -> None:
    coordinator = _coordinator(_complete_options())
    coordinator._house_snapshot_store = _FakeDiagnosticsSource({"total_snapshots": 12})
    coordinator._approval_store = _FakeDiagnosticsSource({"total_records": 1})
    flow = HeimaOptionsFlowHandler(SimpleNamespace(options={}, entry_id="entry-1"))
    flow.hass = SimpleNamespace(
        data={"heima": {"entry-1": {"coordinator": coordinator}}},
        states=SimpleNamespace(async_all=lambda: []),
        config=SimpleNamespace(language="en", time_zone="UTC"),
    )
    flow.context = {"user_id": "user-1"}

    result = await flow.async_step_validation()

    assert result["type"] == "form"
    placeholders = result["description_placeholders"]
    assert placeholders["summary"] == "Installation validation passed."
    assert "Activities:" in placeholders["details"]
