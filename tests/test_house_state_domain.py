from types import SimpleNamespace

import pytest

from custom_components.heima.runtime.domains.calendar import CalendarResult
from custom_components.heima.runtime.domains.events import EventsDomain
from custom_components.heima.runtime.domains.house_state import HouseStateDomain
from custom_components.heima.runtime.inference.signals import HouseStateSignal, Importance
from custom_components.heima.runtime.normalization.service import InputNormalizer


def _fake_hass():
    return SimpleNamespace(
        states=SimpleNamespace(get=lambda _: None),
        services=SimpleNamespace(async_call=None, async_services=lambda: {"notify": {}}),
        bus=SimpleNamespace(async_fire=lambda *a, **kw: None),
    )


def _fake_hass_with_states(entity_states: dict[str, str]):
    def _get(entity_id: str):
        if entity_id not in entity_states:
            return None
        return SimpleNamespace(
            entity_id=entity_id,
            state=entity_states[entity_id],
            attributes={},
        )

    return SimpleNamespace(
        states=SimpleNamespace(get=_get),
        services=SimpleNamespace(async_call=None, async_services=lambda: {"notify": {}}),
        bus=SimpleNamespace(async_fire=lambda *a, **kw: None),
    )


def _fake_state(current_house_state: str | None = None):
    return SimpleNamespace(
        get_sensor=lambda key: current_house_state if key == "heima_house_state" else None,
        get_binary=lambda _: None,
    )


def _house_state_signal(
    predicted_state: str,
    *,
    confidence: float = 0.75,
    source_id: str = "house_state_inference",
    importance: Importance = Importance.SUGGEST,
) -> HouseStateSignal:
    return HouseStateSignal(
        source_id=source_id,
        confidence=confidence,
        importance=importance,
        ttl_s=600,
        label=f"learned:{predicted_state}",
        predicted_state=predicted_state,
    )


def test_house_state_diagnostics_expose_candidate_and_resolution_trace(
    monkeypatch: pytest.MonkeyPatch,
):
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
    assert diagnostics["resolution_trace"]["current_home_state_before"] == "home"
    assert diagnostics["resolution_trace"]["derived_state_direct"] == "working"
    assert diagnostics["resolution_trace"]["resolved_state_after"] == "home"
    assert diagnostics["resolution_trace"]["winning_reason"] == "default"
    assert diagnostics["resolution_trace"]["decision"]["action"] == "pending"
    assert diagnostics["candidate_summary"]["work_candidate"]["status"] == "pending_enter"
    assert diagnostics["candidate_summary"]["relax_candidate"]["status"] == "inactive"

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
    assert diagnostics["resolution_trace"]["decision"]["action"] == "enter"
    assert diagnostics["candidate_summary"]["work_candidate"]["status"] == "confirmed"
    assert diagnostics["config"]["sleep_enter_min"] == 10
    assert diagnostics["config"]["media_active_entities"] == []


def test_house_state_work_activity_required_blocks_work_candidate(
    monkeypatch: pytest.MonkeyPatch,
):
    hass = _fake_hass_with_states({"binary_sensor.stefano_mac_active_recent": "off"})
    normalizer = InputNormalizer(hass)
    domain = HouseStateDomain(hass, normalizer)
    monkeypatch.setattr(
        "custom_components.heima.runtime.domains.house_state.time.monotonic",
        lambda: 3000.0,
    )

    result = domain.compute(
        options={
            "house_state_config": {
                "work_activity_entities": ["binary_sensor.stefano_mac_active_recent"],
                "work_activity_required": True,
            }
        },
        house_signal_entities={},
        anyone_home=True,
        events=EventsDomain(hass),
        state=_fake_state("home"),
        calendar_result=CalendarResult(is_wfh_today=True),
    )

    assert result.house_state == "home"
    assert result.house_reason == "default"
    diagnostics = domain.diagnostics()
    work_trace = diagnostics["candidate_trace"]["work_candidate"]
    assert work_trace["state"] is False
    assert work_trace["inputs"]["work_base_candidate"] is True
    assert work_trace["inputs"]["work_activity_required"] is True
    assert work_trace["inputs"]["work_activity_active"] is False
    assert work_trace["reason"] == "anyone_home+work_window+workday+missing_work_activity"


def test_house_state_work_activity_required_enters_after_activity_threshold(
    monkeypatch: pytest.MonkeyPatch,
):
    hass = _fake_hass_with_states({"binary_sensor.stefano_mac_active_recent": "on"})
    normalizer = InputNormalizer(hass)
    domain = HouseStateDomain(hass, normalizer)
    monotonic = 4000.0
    monkeypatch.setattr(
        "custom_components.heima.runtime.domains.house_state.time.monotonic",
        lambda: monotonic,
    )

    options = {
        "house_state_config": {
            "work_activity_entities": ["binary_sensor.stefano_mac_active_recent"],
            "work_activity_required": True,
        }
    }
    result = domain.compute(
        options=options,
        house_signal_entities={},
        anyone_home=True,
        events=EventsDomain(hass),
        state=_fake_state("home"),
        calendar_result=CalendarResult(is_wfh_today=True),
    )
    assert result.house_state == "home"

    monotonic = 4000.0 + (5 * 60) + 1
    result = domain.compute(
        options=options,
        house_signal_entities={},
        anyone_home=True,
        events=EventsDomain(hass),
        state=_fake_state("home"),
        calendar_result=CalendarResult(is_wfh_today=True),
    )

    assert result.house_state == "working"
    assert result.house_reason == "work_candidate_confirmed"
    assert (
        domain.diagnostics()["candidate_trace"]["work_candidate"]["inputs"]["work_activity_active"]
        is True
    )


def test_house_state_work_activity_grace_retains_working_after_activity_stops(
    monkeypatch: pytest.MonkeyPatch,
):
    entity_states = {"binary_sensor.stefano_mac_active_recent": "on"}
    hass = _fake_hass_with_states(entity_states)
    normalizer = InputNormalizer(hass)
    domain = HouseStateDomain(hass, normalizer)
    monotonic = 5000.0
    monkeypatch.setattr(
        "custom_components.heima.runtime.domains.house_state.time.monotonic",
        lambda: monotonic,
    )
    options = {
        "house_state_config": {
            "work_activity_entities": ["binary_sensor.stefano_mac_active_recent"],
            "work_activity_required": True,
            "work_activity_grace_min": 20,
        }
    }
    domain.compute(
        options=options,
        house_signal_entities={},
        anyone_home=True,
        events=EventsDomain(hass),
        state=_fake_state("home"),
        calendar_result=CalendarResult(is_wfh_today=True),
    )
    monotonic = 5000.0 + (5 * 60) + 1
    entered = domain.compute(
        options=options,
        house_signal_entities={},
        anyone_home=True,
        events=EventsDomain(hass),
        state=_fake_state("home"),
        calendar_result=CalendarResult(is_wfh_today=True),
    )
    assert entered.house_state == "working"

    entity_states["binary_sensor.stefano_mac_active_recent"] = "off"
    monotonic += 10 * 60
    retained = domain.compute(
        options=options,
        house_signal_entities={},
        anyone_home=True,
        events=EventsDomain(hass),
        state=_fake_state("working"),
        calendar_result=CalendarResult(is_wfh_today=True),
    )
    assert retained.house_state == "working"
    assert retained.house_reason == "work_activity_grace"
    assert domain.diagnostics()["resolution_trace"]["decision"]["pending_kind"] == (
        "activity_grace"
    )

    monotonic += 21 * 60
    expired = domain.compute(
        options=options,
        house_signal_entities={},
        anyone_home=True,
        events=EventsDomain(hass),
        state=_fake_state("working"),
        calendar_result=CalendarResult(is_wfh_today=True),
    )
    assert expired.house_state == "home"
    assert expired.house_reason == "default"


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


def test_house_state_learned_signal_influences_when_no_hard_input(
    monkeypatch: pytest.MonkeyPatch,
):
    hass = _fake_hass()
    normalizer = InputNormalizer(hass)
    domain = HouseStateDomain(hass, normalizer)
    monkeypatch.setattr(
        "custom_components.heima.runtime.domains.house_state.time.monotonic",
        lambda: 2500.0,
    )

    result = domain.compute(
        options={},
        house_signal_entities={},
        anyone_home=True,
        events=EventsDomain(hass),
        state=_fake_state("home"),
        calendar_result=None,
        signals=[_house_state_signal("working")],
    )

    assert result.house_state == "working"
    assert result.house_reason == "learned_house_state_signal"
    diagnostics = domain.diagnostics()
    assert diagnostics["resolution_trace"]["decision"]["action"] == "signal"
    assert diagnostics["resolution_trace"]["decision"]["source"] == "house_state_inference"


def test_house_state_learned_signal_ignored_when_override_active(
    monkeypatch: pytest.MonkeyPatch,
):
    hass = _fake_hass()
    normalizer = InputNormalizer(hass)
    domain = HouseStateDomain(hass, normalizer)
    domain.set_override(mode="vacation", enabled=True, source="test")
    monkeypatch.setattr(
        "custom_components.heima.runtime.domains.house_state.time.monotonic",
        lambda: 2550.0,
    )

    result = domain.compute(
        options={},
        house_signal_entities={},
        anyone_home=True,
        events=EventsDomain(hass),
        state=_fake_state("home"),
        calendar_result=None,
        signals=[_house_state_signal("working")],
    )

    assert result.house_state == "vacation"
    assert result.house_reason == "manual_override:vacation"
    assert domain.diagnostics()["resolution_trace"]["resolution_path"] == "override"


def test_house_state_learned_signal_ignored_during_vacation(
    monkeypatch: pytest.MonkeyPatch,
):
    hass = _fake_hass()
    normalizer = InputNormalizer(hass)
    domain = HouseStateDomain(hass, normalizer)
    monkeypatch.setattr(
        "custom_components.heima.runtime.domains.house_state.time.monotonic",
        lambda: 2600.0,
    )

    result = domain.compute(
        options={},
        house_signal_entities={},
        anyone_home=True,
        events=EventsDomain(hass),
        state=_fake_state("home"),
        calendar_result=CalendarResult(is_vacation_active=True),
        signals=[_house_state_signal("working")],
    )

    assert result.house_state == "vacation"
    assert result.house_reason == "vacation_mode"
    assert domain.diagnostics()["resolution_trace"]["resolution_path"] == "hard_state"


def test_house_state_learned_signal_ignored_when_everyone_away(
    monkeypatch: pytest.MonkeyPatch,
):
    hass = _fake_hass()
    normalizer = InputNormalizer(hass)
    domain = HouseStateDomain(hass, normalizer)
    monkeypatch.setattr(
        "custom_components.heima.runtime.domains.house_state.time.monotonic",
        lambda: 2650.0,
    )

    result = domain.compute(
        options={},
        house_signal_entities={},
        anyone_home=False,
        events=EventsDomain(hass),
        state=_fake_state("home"),
        calendar_result=None,
        signals=[_house_state_signal("working")],
    )

    assert result.house_state == "away"
    assert result.house_reason == "no_presence"
    assert domain.diagnostics()["resolution_trace"]["resolution_path"] == "hard_state"


def test_house_state_non_approved_or_low_confidence_signal_has_no_effect(
    monkeypatch: pytest.MonkeyPatch,
):
    hass = _fake_hass()
    normalizer = InputNormalizer(hass)
    domain = HouseStateDomain(hass, normalizer)
    monkeypatch.setattr(
        "custom_components.heima.runtime.domains.house_state.time.monotonic",
        lambda: 2700.0,
    )

    result = domain.compute(
        options={},
        house_signal_entities={},
        anyone_home=True,
        events=EventsDomain(hass),
        state=_fake_state("home"),
        calendar_result=None,
        signals=[
            _house_state_signal("working", source_id="weekday_state"),
            _house_state_signal("relax", confidence=0.59),
        ],
    )

    assert result.house_state == "home"
    assert result.house_reason == "default"
    assert domain.diagnostics()["resolution_trace"]["decision"]["action"] == "fallback_home"


def test_house_state_observe_signal_has_no_effect(
    monkeypatch: pytest.MonkeyPatch,
):
    hass = _fake_hass()
    normalizer = InputNormalizer(hass)
    domain = HouseStateDomain(hass, normalizer)
    monkeypatch.setattr(
        "custom_components.heima.runtime.domains.house_state.time.monotonic",
        lambda: 2750.0,
    )

    result = domain.compute(
        options={},
        house_signal_entities={},
        anyone_home=True,
        events=EventsDomain(hass),
        state=_fake_state("home"),
        calendar_result=None,
        signals=[
            _house_state_signal(
                "working",
                confidence=0.95,
                source_id="house_state_inference",
                importance=Importance.OBSERVE,
            )
        ],
    )

    assert result.house_state == "home"
    assert result.house_reason == "default"
    assert domain.diagnostics()["resolution_trace"]["decision"]["action"] == "fallback_home"


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
                "sleep_charging_entities": ["binary_sensor.phone_charging"],
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
    assert diagnostics["config"]["sleep_charging_entities"] == ["binary_sensor.phone_charging"]
    assert diagnostics["config"]["workday_entity"] == "binary_sensor.workday_sensor"
    assert diagnostics["timers"] == {
        "sleep_enter_min": 12,
        "sleep_exit_min": 4,
        "work_enter_min": 7,
        "work_activity_grace_min": 20,
        "relax_enter_min": 3,
        "relax_exit_min": 11,
    }
    assert (
        diagnostics["candidate_trace"]["sleep_candidate"]["inputs"]["sleep_requires_media_off"]
        is False
    )
    assert (
        diagnostics["candidate_trace"]["sleep_candidate"]["inputs"]["sleep_charging_min_count"] == 2
    )


def test_house_state_signal_trace_marks_unknown_as_treated_false(monkeypatch: pytest.MonkeyPatch):
    def _get(entity_id: str):
        if entity_id == "binary_sensor.work_window":
            return SimpleNamespace(state="unavailable", attributes={})
        return None

    hass = SimpleNamespace(
        states=SimpleNamespace(get=_get),
        services=SimpleNamespace(async_call=None, async_services=lambda: {"notify": {}}),
        bus=SimpleNamespace(async_fire=lambda *a, **kw: None),
    )
    normalizer = InputNormalizer(hass)
    domain = HouseStateDomain(hass, normalizer)
    monkeypatch.setattr(
        "custom_components.heima.runtime.domains.house_state.time.monotonic",
        lambda: 3200.0,
    )

    domain.compute(
        options={},
        house_signal_entities={"work_window": "binary_sensor.work_window"},
        anyone_home=True,
        events=EventsDomain(hass),
        state=_fake_state("home"),
        calendar_result=None,
    )

    trace = domain.diagnostics()["house_signals_trace"]["work_window"]
    assert trace["fused_state"] == "unknown"
    assert trace["resolved_bool"] is False
    assert trace["resolved_reason"] == "derived_unknown_treated_as_false"
    assert trace["has_unknown_inputs"] is True
    assert trace["has_unavailable_inputs"] is True
    assert trace["unknown_inputs"] == ["binary_sensor.work_window"]
    assert trace["unavailable_inputs"] == ["binary_sensor.work_window"]


def test_house_state_sleep_candidate_requires_charging_threshold(monkeypatch: pytest.MonkeyPatch):
    def _get(entity_id: str):
        if entity_id == "binary_sensor.sleep_window":
            return SimpleNamespace(state="on", attributes={})
        if entity_id == "binary_sensor.phone_a_charging":
            return SimpleNamespace(state="on", attributes={})
        if entity_id == "binary_sensor.phone_b_charging":
            return SimpleNamespace(state="off", attributes={})
        return None

    hass = SimpleNamespace(
        states=SimpleNamespace(get=_get),
        services=SimpleNamespace(async_call=None, async_services=lambda: {"notify": {}}),
        bus=SimpleNamespace(async_fire=lambda *a, **kw: None),
    )
    normalizer = InputNormalizer(hass)
    domain = HouseStateDomain(hass, normalizer)
    monkeypatch.setattr(
        "custom_components.heima.runtime.domains.house_state.time.monotonic",
        lambda: 3500.0,
    )

    domain.compute(
        options={
            "house_state_config": {
                "sleep_charging_entities": [
                    "binary_sensor.phone_a_charging",
                    "binary_sensor.phone_b_charging",
                ],
                "sleep_charging_min_count": 2,
            }
        },
        house_signal_entities={"sleep_window": "binary_sensor.sleep_window"},
        anyone_home=True,
        events=EventsDomain(hass),
        state=_fake_state("home"),
        calendar_result=None,
    )
    diagnostics = domain.diagnostics()
    sleep_trace = diagnostics["candidate_trace"]["sleep_candidate"]
    assert sleep_trace["state"] is False
    assert sleep_trace["inputs"]["charging"]["active_count"] == 1
    assert sleep_trace["inputs"]["sleep_charging_requirement_met"] is False


def test_house_state_sleep_candidate_enters_when_charging_threshold_met(
    monkeypatch: pytest.MonkeyPatch,
):
    def _get(entity_id: str):
        if entity_id == "binary_sensor.sleep_window":
            return SimpleNamespace(state="on", attributes={})
        if entity_id in {
            "binary_sensor.phone_a_charging",
            "binary_sensor.phone_b_charging",
        }:
            return SimpleNamespace(state="on", attributes={})
        return None

    hass = SimpleNamespace(
        states=SimpleNamespace(get=_get),
        services=SimpleNamespace(async_call=None, async_services=lambda: {"notify": {}}),
        bus=SimpleNamespace(async_fire=lambda *a, **kw: None),
    )
    normalizer = InputNormalizer(hass)
    domain = HouseStateDomain(hass, normalizer)
    monkeypatch.setattr(
        "custom_components.heima.runtime.domains.house_state.time.monotonic",
        lambda: 3600.0,
    )

    result = domain.compute(
        options={
            "house_state_config": {
                "sleep_charging_entities": [
                    "binary_sensor.phone_a_charging",
                    "binary_sensor.phone_b_charging",
                ],
                "sleep_charging_min_count": 2,
                "sleep_enter_min": 0,
            }
        },
        house_signal_entities={"sleep_window": "binary_sensor.sleep_window"},
        anyone_home=True,
        events=EventsDomain(hass),
        state=_fake_state("home"),
        calendar_result=None,
    )
    assert result.house_state == "sleeping"
    assert result.house_reason == "sleep_candidate_confirmed"


def test_house_state_media_activity_enters_relax_after_timer(monkeypatch: pytest.MonkeyPatch):
    media_state = SimpleNamespace(state="playing", attributes={})
    hass = SimpleNamespace(
        states=SimpleNamespace(
            get=lambda entity_id: media_state if entity_id == "media_player.cineforum" else None
        ),
        services=SimpleNamespace(async_call=None, async_services=lambda: {"notify": {}}),
        bus=SimpleNamespace(async_fire=lambda *a, **kw: None),
    )
    normalizer = InputNormalizer(hass)
    domain = HouseStateDomain(hass, normalizer)
    monotonic = 4000.0
    monkeypatch.setattr(
        "custom_components.heima.runtime.domains.house_state.time.monotonic",
        lambda: monotonic,
    )
    options = {"house_state_config": {"media_active_entities": ["media_player.cineforum"]}}

    result = domain.compute(
        options=options,
        house_signal_entities={},
        anyone_home=True,
        events=EventsDomain(hass),
        state=_fake_state("home"),
        calendar_result=None,
    )
    assert result.house_state == "home"
    diagnostics = domain.diagnostics()
    assert diagnostics["candidate_trace"]["relax_candidate"]["state"] is True
    assert diagnostics["candidate_trace"]["relax_candidate"]["reason"] == "anyone_home+media_active"
    assert diagnostics["candidate_trace"]["relax_candidate"]["inputs"]["media_active"] is True

    monotonic += (2 * 60) + 1
    result = domain.compute(
        options=options,
        house_signal_entities={},
        anyone_home=True,
        events=EventsDomain(hass),
        state=_fake_state("home"),
        calendar_result=None,
    )
    assert result.house_state == "relax"
    assert result.house_reason == "relax_candidate_confirmed"
    diagnostics = domain.diagnostics()
    assert diagnostics["resolution_trace"]["decision"]["action"] == "enter"
    assert diagnostics["candidate_summary"]["relax_candidate"]["status"] == "confirmed"


def test_house_state_sleep_candidate_blocked_when_media_active(monkeypatch: pytest.MonkeyPatch):
    sleep_state = SimpleNamespace(state="on", attributes={})
    media_state = SimpleNamespace(state="paused", attributes={})

    def _get(entity_id: str):
        if entity_id == "binary_sensor.sleep_window":
            return sleep_state
        if entity_id == "media_player.cineforum":
            return media_state
        return None

    hass = SimpleNamespace(
        states=SimpleNamespace(get=_get),
        services=SimpleNamespace(async_call=None, async_services=lambda: {"notify": {}}),
        bus=SimpleNamespace(async_fire=lambda *a, **kw: None),
    )
    normalizer = InputNormalizer(hass)
    domain = HouseStateDomain(hass, normalizer)
    monkeypatch.setattr(
        "custom_components.heima.runtime.domains.house_state.time.monotonic",
        lambda: 5000.0,
    )

    domain.compute(
        options={"house_state_config": {"media_active_entities": ["media_player.cineforum"]}},
        house_signal_entities={"sleep_window": "binary_sensor.sleep_window"},
        anyone_home=True,
        events=EventsDomain(hass),
        state=_fake_state("home"),
        calendar_result=None,
    )
    diagnostics = domain.diagnostics()
    assert diagnostics["candidate_trace"]["sleep_candidate"]["state"] is False
    assert diagnostics["candidate_trace"]["sleep_candidate"]["inputs"]["media_active"] is True
    assert (
        diagnostics["candidate_trace"]["sleep_candidate"]["inputs"]["sleep_media_requirement_met"]
        is False
    )
    assert diagnostics["candidate_trace"]["wake_candidate"]["state"] is True
    assert diagnostics["candidate_trace"]["wake_candidate"]["reason"] == "anyone_home+media_active"


def test_house_state_work_candidate_blocked_by_calendar_office(monkeypatch: pytest.MonkeyPatch):
    workday_state = SimpleNamespace(state="on", attributes={})
    hass = SimpleNamespace(
        states=SimpleNamespace(
            get=lambda entity_id: workday_state if entity_id == "binary_sensor.workday" else None
        ),
        services=SimpleNamespace(async_call=None, async_services=lambda: {"notify": {}}),
        bus=SimpleNamespace(async_fire=lambda *a, **kw: None),
    )
    normalizer = InputNormalizer(hass)
    domain = HouseStateDomain(hass, normalizer)
    monotonic = 6000.0
    monkeypatch.setattr(
        "custom_components.heima.runtime.domains.house_state.time.monotonic",
        lambda: monotonic,
    )
    options = {"house_state_config": {"workday_entity": "binary_sensor.workday"}}

    result = domain.compute(
        options=options,
        house_signal_entities={"work_window": "binary_sensor.work_window"},
        anyone_home=True,
        events=EventsDomain(hass),
        state=_fake_state("home"),
        calendar_result=CalendarResult(is_office_today=True),
    )
    assert result.house_state == "home"
    diagnostics = domain.diagnostics()
    assert diagnostics["candidate_trace"]["work_candidate"]["state"] is False
    assert (
        diagnostics["candidate_trace"]["work_candidate"]["inputs"]["workday_evidence"]["source"]
        == "calendar_office"
    )


def test_house_state_work_candidate_uses_workday_entity_when_calendar_neutral(
    monkeypatch: pytest.MonkeyPatch,
):
    def _get(entity_id: str):
        if entity_id == "binary_sensor.work_window":
            return SimpleNamespace(state="on", attributes={})
        if entity_id == "binary_sensor.workday":
            return SimpleNamespace(state="off", attributes={})
        return None

    hass = SimpleNamespace(
        states=SimpleNamespace(get=_get),
        services=SimpleNamespace(async_call=None, async_services=lambda: {"notify": {}}),
        bus=SimpleNamespace(async_fire=lambda *a, **kw: None),
    )
    normalizer = InputNormalizer(hass)
    domain = HouseStateDomain(hass, normalizer)
    monotonic = 7000.0
    monkeypatch.setattr(
        "custom_components.heima.runtime.domains.house_state.time.monotonic",
        lambda: monotonic,
    )

    domain.compute(
        options={"house_state_config": {"workday_entity": "binary_sensor.workday"}},
        house_signal_entities={"work_window": "binary_sensor.work_window"},
        anyone_home=True,
        events=EventsDomain(hass),
        state=_fake_state("home"),
        calendar_result=None,
    )
    diagnostics = domain.diagnostics()
    assert diagnostics["candidate_trace"]["work_candidate"]["state"] is False
    assert (
        diagnostics["candidate_trace"]["work_candidate"]["inputs"]["workday_evidence"]["source"]
        == "workday_entity"
    )
    assert (
        diagnostics["candidate_trace"]["work_candidate"]["inputs"]["workday_evidence"]["is_workday"]
        is False
    )


def test_house_state_work_candidate_calendar_wfh_overrides_workday_entity(
    monkeypatch: pytest.MonkeyPatch,
):
    def _get(entity_id: str):
        if entity_id == "binary_sensor.work_window":
            return SimpleNamespace(state="on", attributes={})
        if entity_id == "binary_sensor.workday":
            return SimpleNamespace(state="off", attributes={})
        return None

    hass = SimpleNamespace(
        states=SimpleNamespace(get=_get),
        services=SimpleNamespace(async_call=None, async_services=lambda: {"notify": {}}),
        bus=SimpleNamespace(async_fire=lambda *a, **kw: None),
    )
    normalizer = InputNormalizer(hass)
    domain = HouseStateDomain(hass, normalizer)
    monotonic = 8000.0
    monkeypatch.setattr(
        "custom_components.heima.runtime.domains.house_state.time.monotonic",
        lambda: monotonic,
    )
    options = {"house_state_config": {"workday_entity": "binary_sensor.workday"}}

    domain.compute(
        options=options,
        house_signal_entities={"work_window": "binary_sensor.work_window"},
        anyone_home=True,
        events=EventsDomain(hass),
        state=_fake_state("home"),
        calendar_result=CalendarResult(is_wfh_today=True),
    )
    diagnostics = domain.diagnostics()
    assert diagnostics["candidate_trace"]["work_candidate"]["state"] is True
    assert (
        diagnostics["candidate_trace"]["work_candidate"]["inputs"]["workday_evidence"]["source"]
        == "calendar_wfh"
    )

    monotonic += (5 * 60) + 1
    result = domain.compute(
        options=options,
        house_signal_entities={"work_window": "binary_sensor.work_window"},
        anyone_home=True,
        events=EventsDomain(hass),
        state=_fake_state("home"),
        calendar_result=CalendarResult(is_wfh_today=True),
    )
    assert result.house_state == "working"
