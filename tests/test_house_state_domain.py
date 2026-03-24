from types import SimpleNamespace

import pytest

from custom_components.heima.runtime.domains.calendar import CalendarResult
from custom_components.heima.runtime.domains.events import EventsDomain
from custom_components.heima.runtime.domains.house_state import HouseStateDomain
from custom_components.heima.runtime.normalization.service import InputNormalizer


def _fake_hass():
    return SimpleNamespace(
        states=SimpleNamespace(get=lambda _: None),
        services=SimpleNamespace(async_call=None, async_services=lambda: {"notify": {}}),
        bus=SimpleNamespace(async_fire=lambda *a, **kw: None),
    )


def _fake_state(current_house_state: str | None = None):
    return SimpleNamespace(
        get_sensor=lambda key: current_house_state if key == "heima_house_state" else None,
        get_binary=lambda _: None,
    )


def test_house_state_diagnostics_expose_candidate_and_resolution_trace(monkeypatch: pytest.MonkeyPatch):
    hass = _fake_hass()
    normalizer = InputNormalizer(hass)
    domain = HouseStateDomain(hass, normalizer)
    monotonic = 1000.0
    monkeypatch.setattr(
        "custom_components.heima.runtime.domains.house_state.time.monotonic",
        lambda: monotonic,
    )
    result = domain.compute(
        options={},
        house_signal_entities={},
        anyone_home=True,
        events=EventsDomain(hass),
        state=_fake_state("home"),
        calendar_result=CalendarResult(is_wfh_today=True),
    )

    assert result.house_state == "home"

    diagnostics = domain.diagnostics()
    assert diagnostics["timers"]["sleep_enter_min"] == 10
    assert diagnostics["candidate_trace"]["work_candidate"]["state"] is True
    assert diagnostics["candidate_trace"]["relax_candidate"]["state"] is False
    assert diagnostics["candidate_trace"]["sleep_candidate"]["state_since"] is not None
    assert diagnostics["resolution_trace"]["current_state_before"] == "home"
    assert diagnostics["resolution_trace"]["derived_state_direct"] == "working"
    assert diagnostics["resolution_trace"]["resolved_state_after"] == "home"
    assert diagnostics["resolution_trace"]["winning_reason"] == "default"

    monotonic = 1000.0 + (5 * 60) + 1
    result = domain.compute(
        options={},
        house_signal_entities={},
        anyone_home=True,
        events=EventsDomain(hass),
        state=_fake_state("home"),
        calendar_result=CalendarResult(is_wfh_today=True),
    )
    assert result.house_state == "working"
    diagnostics = domain.diagnostics()
    assert diagnostics["resolution_trace"]["resolved_state_after"] == "working"
    assert diagnostics["resolution_trace"]["winning_reason"] == "work_candidate_confirmed"
    assert diagnostics["config"]["sleep_enter_min"] == 10
    assert diagnostics["config"]["media_active_entities"] == []


def test_house_state_relax_mode_is_immediate(monkeypatch: pytest.MonkeyPatch):
    relax_state = SimpleNamespace(state="on", attributes={})
    hass = SimpleNamespace(
        states=SimpleNamespace(
            get=lambda entity_id: relax_state if entity_id == "input_boolean.relax" else None
        ),
        services=SimpleNamespace(async_call=None, async_services=lambda: {"notify": {}}),
        bus=SimpleNamespace(async_fire=lambda *a, **kw: None),
    )
    normalizer = InputNormalizer(hass)
    domain = HouseStateDomain(hass, normalizer)
    monkeypatch.setattr(
        "custom_components.heima.runtime.domains.house_state.time.monotonic",
        lambda: 2000.0,
    )
    result = domain.compute(
        options={},
        house_signal_entities={"relax_mode": "input_boolean.relax"},
        anyone_home=True,
        events=EventsDomain(hass),
        state=_fake_state("home"),
        calendar_result=None,
    )
    assert result.house_state == "relax"
    assert result.house_reason == "relax_explicit_signal"


def test_house_state_domain_reads_persisted_house_state_config(monkeypatch: pytest.MonkeyPatch):
    hass = _fake_hass()
    normalizer = InputNormalizer(hass)
    domain = HouseStateDomain(hass, normalizer)
    monkeypatch.setattr(
        "custom_components.heima.runtime.domains.house_state.time.monotonic",
        lambda: 3000.0,
    )
    domain.compute(
        options={
            "house_state_config": {
                "media_active_entities": ["media_player.cineforum"],
                "workday_entity": "binary_sensor.workday_sensor",
                "sleep_enter_min": 12,
                "sleep_exit_min": 4,
                "work_enter_min": 7,
                "relax_enter_min": 3,
                "relax_exit_min": 11,
                "sleep_requires_media_off": False,
                "sleep_charging_min_count": 2,
            }
        },
        house_signal_entities={},
        anyone_home=True,
        events=EventsDomain(hass),
        state=_fake_state("home"),
        calendar_result=None,
    )
    diagnostics = domain.diagnostics()
    assert diagnostics["config"]["media_active_entities"] == ["media_player.cineforum"]
    assert diagnostics["config"]["workday_entity"] == "binary_sensor.workday_sensor"
    assert diagnostics["timers"] == {
        "sleep_enter_min": 12,
        "sleep_exit_min": 4,
        "work_enter_min": 7,
        "relax_enter_min": 3,
        "relax_exit_min": 11,
    }
    assert diagnostics["candidate_trace"]["sleep_candidate"]["inputs"]["sleep_requires_media_off"] is False
    assert diagnostics["candidate_trace"]["sleep_candidate"]["inputs"]["sleep_charging_min_count"] == 2
