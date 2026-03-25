from __future__ import annotations

from types import SimpleNamespace

import pytest

from custom_components.heima.runtime.engine import HeimaEngine


class _FakeStateObj:
    def __init__(self, state: str, attributes: dict[str, object] | None = None):
        self.state = state
        self.attributes = dict(attributes or {})


class _FakeStates:
    def __init__(self, values: dict[str, object] | None = None):
        self._values = dict(values or {})

    def get(self, entity_id: str):
        value = self._values.get(entity_id)
        if value is None:
            return None
        if isinstance(value, tuple):
            state, attrs = value
            return _FakeStateObj(str(state), attrs)
        return _FakeStateObj(str(value))


class _FakeBus:
    def __init__(self):
        self.events: list[tuple[str, dict]] = []

    def async_fire(self, event_type, data):
        self.events.append((event_type, dict(data)))
        return None


class _FakeServices:
    def __init__(self):
        self.calls: list[tuple[str, str, dict, bool]] = []

    async def async_call(self, domain, service, data, blocking=False):
        self.calls.append((domain, service, dict(data), blocking))

    def async_services(self):
        return {"notify": {}}


def _entry_with_options(options: dict) -> SimpleNamespace:
    return SimpleNamespace(options=options)


def _build_engine(
    options: dict,
    state_values: dict[str, object] | None = None,
) -> HeimaEngine:
    hass = SimpleNamespace(
        states=_FakeStates(state_values),
        services=_FakeServices(),
        bus=_FakeBus(),
    )
    engine = HeimaEngine(hass=hass, entry=_entry_with_options(options))
    engine._build_default_state()
    return engine


def _with_house_signal_binding(options: dict, **bindings: str) -> dict:
    merged = dict(options)
    current = dict(merged.get("house_signals", {}))
    current.update({key: value for key, value in bindings.items() if value})
    merged["house_signals"] = current
    return merged


@pytest.mark.asyncio
async def test_fixed_target_branch_builds_and_executes_heating_apply_step():
    options = {
        "heating": {
            "climate_entity": "climate.test_thermostat",
            "apply_mode": "set_temperature",
            "temperature_step": 0.5,
            "manual_override_guard": True,
            "override_branches": {
                "away": {
                    "branch": "fixed_target",
                    "target_temperature": 20.0,
                }
            },
        }
    }
    engine = _build_engine(
        options,
        {
            "climate.test_thermostat": ("heat", {"temperature": 18.0}),
        },
    )

    snapshot = engine._compute_snapshot(reason="test")
    plan = engine._build_apply_plan(snapshot)

    assert engine.state.get_sensor("heima_heating_state") == "target_active"
    assert engine.state.get_sensor("heima_heating_reason") == "fixed_target_branch"
    assert engine.state.get_sensor("heima_heating_phase") == "fixed_target"
    assert engine.state.get_sensor("heima_heating_branch") == "fixed_target"
    assert engine.state.get_sensor("heima_heating_target_temp") == 20.0
    assert engine.state.get_sensor("heima_heating_current_setpoint") == 18.0
    assert any(step.action == "climate.set_temperature" for step in plan.steps)

    await engine._execute_apply_plan(plan)

    assert engine._hass.services.calls[-1] == (
        "climate",
        "set_temperature",
        {
            "entity_id": "climate.test_thermostat",
            "temperature": 20.0,
        },
        False,
    )
    assert engine.state.get_sensor("heima_heating_last_applied_target") == 20.0


@pytest.mark.asyncio
async def test_runtime_reload_preserves_house_state_progress_for_unrelated_option_change(
    monkeypatch: pytest.MonkeyPatch,
):
    options = _with_house_signal_binding(
        {
            "language": "en",
            "people_named": [
                {
                    "slug": "stefano",
                    "display_name": "Stefano",
                    "presence_method": "ha_person",
                    "person_entity": "person.stefano",
                }
            ],
            "house_state_config": {
                "work_enter_min": 5,
            },
        },
        work_window="binary_sensor.work_window",
    )
    engine = _build_engine(
        options,
        {
            "person.stefano": "home",
            "binary_sensor.work_window": "on",
        },
    )

    monotonic = 1000.0
    monkeypatch.setattr(
        "custom_components.heima.runtime.domains.house_state.time.monotonic",
        lambda: monotonic,
    )

    first = engine._compute_snapshot(reason="before_reload")
    assert first.house_state == "home"
    initial_pending = engine.state.get_sensor("heima_house_state_pending_remaining_s")
    assert isinstance(initial_pending, float)
    assert initial_pending > 290

    monotonic = 1000.0 + (5 * 60) - 1
    updated_options = dict(options)
    updated_options["language"] = "it"
    await engine.async_reload_options(
        _entry_with_options(updated_options),
        changed_keys={"language"},
    )

    pending_after_reload = engine.state.get_sensor("heima_house_state_pending_remaining_s")
    assert isinstance(pending_after_reload, float)
    assert pending_after_reload < 2

    monotonic = 1000.0 + (5 * 60) + 1
    second = engine._compute_snapshot(reason="after_reload")
    assert second.house_state == "working"


def test_heating_snapshot_uses_observed_current_setpoint_not_target():
    options = {
        "heating": {
            "climate_entity": "climate.test_thermostat",
            "apply_mode": "set_temperature",
            "temperature_step": 0.5,
            "manual_override_guard": True,
            "override_branches": {
                "away": {
                    "branch": "fixed_target",
                    "target_temperature": 20.0,
                }
            },
        }
    }
    engine = _build_engine(
        options,
        {
            "climate.test_thermostat": ("heat", {"temperature": 18.0}),
        },
    )

    snapshot = engine._compute_snapshot(reason="test")

    assert snapshot.heating_setpoint == 18.0
    assert engine.diagnostics()["heating"]["target_temperature"] == 20.0


def test_house_state_diagnostics_are_exposed_as_state_entities_and_attributes():
    options = _with_house_signal_binding(
        {
            "people_named": [
                {
                    "slug": "stefano",
                    "display_name": "Stefano",
                    "presence_method": "ha_person",
                    "person_entity": "person.stefano",
                }
            ],
            "house_state_config": {
                "work_enter_min": 5,
            },
        },
        work_window="binary_sensor.work_window",
    )
    engine = _build_engine(
        options,
        {
            "person.stefano": "home",
            "binary_sensor.work_window": "on",
        },
    )

    snapshot = engine._compute_snapshot(reason="test")

    assert snapshot.house_state == "home"
    assert engine.state.get_sensor("heima_house_state") == "home"
    assert engine.state.get_sensor("heima_house_state_reason") == "default"
    assert engine.state.get_sensor("heima_house_state_path") == "home_substate"
    assert engine.state.get_sensor("heima_house_state_active_candidates") == "wake_candidate,work_candidate"
    assert engine.state.get_sensor("heima_house_state_pending_candidate") == "work_candidate"
    pending_remaining = engine.state.get_sensor("heima_house_state_pending_remaining_s")
    assert isinstance(pending_remaining, float)
    assert pending_remaining > 0
    attrs = engine.state.get_sensor_attributes("heima_house_state") or {}
    assert attrs["resolution_trace"]["decision"]["action"] == "pending"
    assert attrs["candidate_summary"]["work_candidate"]["status"] == "pending_enter"


def test_build_default_state_clears_stale_sensor_attributes():
    options = _with_house_signal_binding(
        {
            "people_named": [
                {
                    "slug": "stefano",
                    "display_name": "Stefano",
                    "presence_method": "ha_person",
                    "person_entity": "person.stefano",
                }
            ]
        },
        work_window="binary_sensor.work_window",
    )
    engine = _build_engine(
        options,
        {
            "person.stefano": "home",
            "binary_sensor.work_window": "on",
        },
    )

    engine._compute_snapshot(reason="test")
    assert engine.state.get_sensor_attributes("heima_house_state") is not None
    assert engine.state.get_sensor_attributes("heima_house_state_reason") is not None

    engine._build_default_state()

    assert engine.state.get_sensor_attributes("heima_house_state") is None
    assert engine.state.get_sensor_attributes("heima_house_state_reason") is None


def test_heating_snapshot_marks_observed_setpoint_as_heima_after_matching_apply():
    options = {
        "heating": {
            "climate_entity": "climate.test_thermostat",
            "apply_mode": "set_temperature",
            "temperature_step": 0.5,
            "manual_override_guard": True,
            "override_branches": {
                "away": {
                    "branch": "fixed_target",
                    "target_temperature": 20.0,
                }
            },
        }
    }
    engine = _build_engine(
        options,
        {
            "climate.test_thermostat": ("heat", {"temperature": 18.0}),
        },
    )

    _ = engine._compute_snapshot(reason="before_apply")
    engine._heating_domain.mark_applied(
        20.0,
        source="reaction:heat_pref_test",
        origin_reaction_id="heat_pref_test",
        origin_reaction_class="HeatingPreferenceReaction",
        climate_entity="climate.test_thermostat",
    )
    engine._hass.states._values["climate.test_thermostat"] = ("heat", {"temperature": 20.0})

    snapshot = engine._compute_snapshot(reason="after_apply")

    assert snapshot.heating_setpoint == 20.0
    assert snapshot.heating_source == "heima"
    assert snapshot.heating_provenance == {
        "source": "reaction:heat_pref_test",
        "origin_reaction_id": "heat_pref_test",
        "origin_reaction_class": "HeatingPreferenceReaction",
        "expected_domains": ["climate"],
        "expected_subject_ids": ["climate.test_thermostat"],
    }


def test_heating_snapshot_marks_observed_setpoint_as_user_when_not_matching_last_heima_apply():
    options = {
        "heating": {
            "climate_entity": "climate.test_thermostat",
            "apply_mode": "set_temperature",
            "temperature_step": 0.5,
            "manual_override_guard": True,
            "override_branches": {
                "away": {
                    "branch": "fixed_target",
                    "target_temperature": 20.0,
                }
            },
        }
    }
    engine = _build_engine(
        options,
        {
            "climate.test_thermostat": ("heat", {"temperature": 18.0}),
        },
    )

    _ = engine._compute_snapshot(reason="before_apply")
    engine._heating_domain.mark_applied(
        20.0,
        source="reaction:heat_pref_test",
        origin_reaction_id="heat_pref_test",
        origin_reaction_class="HeatingPreferenceReaction",
        climate_entity="climate.test_thermostat",
    )
    engine._hass.states._values["climate.test_thermostat"] = ("heat", {"temperature": 21.5})

    snapshot = engine._compute_snapshot(reason="manual_change")

    assert snapshot.heating_setpoint == 21.5
    assert snapshot.heating_source == "user"
    assert snapshot.heating_provenance is None


def test_fixed_target_branch_skips_small_delta_and_sets_guard():
    options = {
        "heating": {
            "climate_entity": "climate.test_thermostat",
            "apply_mode": "set_temperature",
            "temperature_step": 0.5,
            "manual_override_guard": True,
            "override_branches": {
                "away": {
                    "branch": "fixed_target",
                    "target_temperature": 20.0,
                }
            },
        }
    }
    engine = _build_engine(
        options,
        {
            "climate.test_thermostat": ("heat", {"temperature": 19.8}),
        },
    )

    snapshot = engine._compute_snapshot(reason="test")
    plan = engine._build_apply_plan(snapshot)

    assert snapshot.house_state == "away"
    assert engine.state.get_sensor("heima_heating_state") == "idle"
    assert engine.state.get_sensor("heima_heating_reason") == "small_delta_skip"
    assert engine.state.get_binary("heima_heating_applying_guard") is True
    assert not any(step.action == "climate.set_temperature" for step in plan.steps)


def test_fixed_target_branch_blocks_on_climate_manual_preset_override():
    options = {
        "heating": {
            "climate_entity": "climate.test_thermostat",
            "apply_mode": "set_temperature",
            "temperature_step": 0.5,
            "manual_override_guard": True,
            "override_branches": {
                "away": {
                    "branch": "fixed_target",
                    "target_temperature": 20.0,
                }
            },
        }
    }
    engine = _build_engine(
        options,
        {
            "climate.test_thermostat": ("heat", {"temperature": 18.0, "preset_mode": "PermanentHold"}),
        },
    )

    snapshot = engine._compute_snapshot(reason="test")
    plan = engine._build_apply_plan(snapshot)
    trace = engine.diagnostics()["heating"]

    assert snapshot.house_state == "away"
    assert engine.state.get_sensor("heima_heating_state") == "blocked"
    assert engine.state.get_sensor("heima_heating_reason") == "manual_override_blocked"
    assert engine.state.get_binary("heima_heating_applying_guard") is True
    assert not any(step.action == "climate.set_temperature" for step in plan.steps)
    assert trace["climate_preset_mode"] == "PermanentHold"
    assert trace["manual_override_source"] == "climate_preset"


def test_heating_without_active_override_branch_delegates_to_scheduler():
    options = {
        "heating": {
            "climate_entity": "climate.test_thermostat",
            "apply_mode": "delegate_to_scheduler",
            "temperature_step": 0.5,
            "manual_override_guard": True,
            "override_branches": {
                "vacation": {
                    "branch": "fixed_target",
                    "target_temperature": 18.0,
                }
            },
        }
    }
    engine = _build_engine(
        options,
        {
            "climate.test_thermostat": ("heat", {"temperature": 18.0}),
        },
    )

    snapshot = engine._compute_snapshot(reason="test")
    plan = engine._build_apply_plan(snapshot)
    trace = engine.diagnostics()["heating"]

    assert snapshot.house_state == "away"
    assert engine.state.get_sensor("heima_heating_state") == "delegated"
    assert engine.state.get_sensor("heima_heating_reason") == "normal_scheduler_delegate"
    assert engine.state.get_sensor("heima_heating_phase") == "normal"
    assert engine.state.get_sensor("heima_heating_branch") == "disabled"
    assert engine.state.get_sensor("heima_heating_target_temp") is None
    assert not any(step.domain == "heating" for step in plan.steps)
    assert trace["selected_branch"] == "disabled"
    assert trace["apply_allowed"] is False


def test_heating_vacation_recheck_delay_prefers_next_quantized_target_change():
    delay_s = HeimaEngine._heating_vacation_recheck_delay_s(
        phase="ramp_down",
        vacation_meta={
            "hours_from_start": 2.0,
            "hours_to_end": 30.0,
            "ramp_down_h": 8.0,
            "ramp_up_h": 10.0,
            "start_temp": 19.5,
            "comfort_temp": 19.5,
            "min_safety": 16.5,
            "raw_target": 18.875,
            "quantized_target": 19.0,
        },
        temperature_step=0.5,
    )

    assert delay_s is not None
    assert delay_s == pytest.approx(1200.0)


@pytest.mark.asyncio
async def test_vacation_curve_branch_computes_target_and_executes_apply():
    options = _with_house_signal_binding(
        {
        "heating": {
            "climate_entity": "climate.test_thermostat",
            "apply_mode": "set_temperature",
            "temperature_step": 0.5,
            "manual_override_guard": True,
            "outdoor_temperature_entity": "sensor.outdoor_temp",
            "vacation_hours_from_start_entity": "sensor.vacation_from",
            "vacation_hours_to_end_entity": "sensor.vacation_to",
            "vacation_total_hours_entity": "sensor.vacation_total",
            "vacation_is_long_entity": "binary_sensor.vacation_long",
            "override_branches": {
                "vacation": {
                    "branch": "vacation_curve",
                    "vacation_ramp_down_h": 8.0,
                    "vacation_ramp_up_h": 10.0,
                    "vacation_min_temp": 16.5,
                    "vacation_comfort_temp": 19.5,
                    "vacation_min_total_hours_for_ramp": 24.0,
                }
            },
        }
    },
        vacation_mode="input_boolean.vacation_mode",
    )
    engine = _build_engine(
        options,
        {
            "input_boolean.vacation_mode": "on",
            "climate.test_thermostat": ("heat", {"temperature": 18.0}),
            "sensor.outdoor_temp": "5.0",
            "sensor.vacation_from": "2.0",
            "sensor.vacation_to": "30.0",
            "sensor.vacation_total": "32.0",
            "binary_sensor.vacation_long": "on",
        },
    )

    snapshot = engine._compute_snapshot(reason="test")
    plan = engine._build_apply_plan(snapshot)

    assert snapshot.house_state == "vacation"
    assert engine.state.get_sensor("heima_heating_state") == "target_active"
    assert engine.state.get_sensor("heima_heating_reason") == "vacation_curve_branch"
    assert engine.state.get_sensor("heima_heating_phase") == "ramp_down"
    assert engine.state.get_sensor("heima_heating_branch") == "vacation_curve"
    assert engine.state.get_sensor("heima_heating_target_temp") == 17.5
    assert any(step.action == "climate.set_temperature" for step in plan.steps)

    await engine._execute_apply_plan(plan)

    assert engine._hass.services.calls[-1] == (
        "climate",
        "set_temperature",
        {
            "entity_id": "climate.test_thermostat",
            "temperature": 17.5,
        },
        False,
    )
    trace = engine.diagnostics()["heating"]
    assert trace["vacation"]["is_long"] is True
    assert trace["vacation"]["raw_target"] == 17.625
    assert trace["vacation"]["return_preheat_target"] == 19.5
    assert trace["vacation"]["scheduler_handoff_on_exit"] is True
    assert trace["vacation"]["start_temp"] == 18.0


def test_vacation_curve_captures_start_temperature_on_branch_activation_and_reuses_it():
    options = _with_house_signal_binding(
        {
            "heating": {
                "climate_entity": "climate.test_thermostat",
                "apply_mode": "set_temperature",
                "temperature_step": 0.5,
                "manual_override_guard": True,
                "outdoor_temperature_entity": "sensor.outdoor_temp",
                "vacation_hours_from_start_entity": "sensor.vacation_from",
                "vacation_hours_to_end_entity": "sensor.vacation_to",
                "vacation_total_hours_entity": "sensor.vacation_total",
                "vacation_is_long_entity": "binary_sensor.vacation_long",
                "override_branches": {
                    "vacation": {
                        "branch": "vacation_curve",
                        "vacation_ramp_down_h": 8.0,
                        "vacation_ramp_up_h": 10.0,
                        "vacation_min_temp": 16.5,
                        "vacation_comfort_temp": 19.5,
                        "vacation_min_total_hours_for_ramp": 24.0,
                    }
                },
            }
        },
        vacation_mode="input_boolean.vacation_mode",
    )
    engine = _build_engine(
        options,
        {
            "input_boolean.vacation_mode": "on",
            "climate.test_thermostat": ("heat", {"temperature": 21.0}),
            "sensor.outdoor_temp": "5.0",
            "sensor.vacation_from": "2.0",
            "sensor.vacation_to": "30.0",
            "sensor.vacation_total": "32.0",
            "binary_sensor.vacation_long": "on",
        },
    )

    engine._compute_snapshot(reason="first")
    assert engine.diagnostics()["heating"]["vacation"]["start_temp"] == 21.0

    engine._hass.states._values["climate.test_thermostat"] = ("heat", {"temperature": 17.0})
    engine._compute_snapshot(reason="second")
    assert engine.diagnostics()["heating"]["vacation"]["start_temp"] == 21.0


@pytest.mark.asyncio
async def test_heating_runtime_emits_phase_and_target_events_for_vacation_curve():
    options = _with_house_signal_binding(
        {
        "heating": {
            "climate_entity": "climate.test_thermostat",
            "apply_mode": "set_temperature",
            "temperature_step": 0.5,
            "manual_override_guard": True,
            "outdoor_temperature_entity": "sensor.outdoor_temp",
            "vacation_hours_from_start_entity": "sensor.vacation_from",
            "vacation_hours_to_end_entity": "sensor.vacation_to",
            "vacation_total_hours_entity": "sensor.vacation_total",
            "vacation_is_long_entity": "binary_sensor.vacation_long",
            "override_branches": {
                "vacation": {
                    "branch": "vacation_curve",
                    "vacation_ramp_down_h": 8.0,
                    "vacation_ramp_up_h": 10.0,
                    "vacation_min_temp": 16.5,
                    "vacation_comfort_temp": 19.5,
                    "vacation_min_total_hours_for_ramp": 24.0,
                }
            },
        }
    },
        vacation_mode="input_boolean.vacation_mode",
    )
    engine = _build_engine(
        options,
        {
            "input_boolean.vacation_mode": "on",
            "climate.test_thermostat": ("heat", {"temperature": 18.0}),
            "sensor.outdoor_temp": "5.0",
            "sensor.vacation_from": "2.0",
            "sensor.vacation_to": "30.0",
            "sensor.vacation_total": "32.0",
            "binary_sensor.vacation_long": "on",
        },
    )

    await engine.async_evaluate(reason="test")

    event_types = [event_type for event_type, _ in engine._hass.bus.events]
    assert "heima_event" in event_types
    payloads = [payload for event_type, payload in engine._hass.bus.events if event_type == "heima_event"]
    types = [payload["type"] for payload in payloads]
    assert "heating.vacation_phase_changed" in types
    assert "heating.target_changed" in types


@pytest.mark.asyncio
async def test_heating_runtime_emits_branch_changed_event_on_transition():
    options = _with_house_signal_binding(
        {
        "heating": {
            "climate_entity": "climate.test_thermostat",
            "apply_mode": "set_temperature",
            "temperature_step": 0.5,
            "manual_override_guard": True,
            "override_branches": {
                "away": {"branch": "fixed_target", "target_temperature": 18.0},
                "vacation": {
                    "branch": "vacation_curve",
                    "vacation_ramp_down_h": 8.0,
                    "vacation_ramp_up_h": 10.0,
                    "vacation_min_temp": 16.5,
                    "vacation_comfort_temp": 19.5,
                    "vacation_min_total_hours_for_ramp": 24.0,
                },
            },
            "outdoor_temperature_entity": "sensor.outdoor_temp",
            "vacation_hours_from_start_entity": "sensor.vacation_from",
            "vacation_hours_to_end_entity": "sensor.vacation_to",
            "vacation_total_hours_entity": "sensor.vacation_total",
            "vacation_is_long_entity": "binary_sensor.vacation_long",
        }
    },
        vacation_mode="input_boolean.vacation_mode",
    )
    engine = _build_engine(
        options,
        {
            "climate.test_thermostat": ("heat", {"temperature": 18.0}),
            "sensor.outdoor_temp": "5.0",
            "sensor.vacation_from": "2.0",
            "sensor.vacation_to": "30.0",
            "sensor.vacation_total": "32.0",
            "binary_sensor.vacation_long": "on",
        },
    )

    await engine.async_evaluate(reason="away")
    engine._hass.states._values["input_boolean.vacation_mode"] = "on"
    await engine.async_evaluate(reason="vacation")

    payloads = [payload for event_type, payload in engine._hass.bus.events if event_type == "heima_event"]
    branch_events = [payload for payload in payloads if payload["type"] == "heating.branch_changed"]

    assert len(branch_events) == 1
    assert branch_events[0]["context"]["previous"] == "fixed_target"
    assert branch_events[0]["context"]["current"] == "vacation_curve"


@pytest.mark.asyncio
async def test_heating_runtime_emits_manual_override_blocked_event_once_per_transition():
    options = {
        "heating": {
            "climate_entity": "climate.test_thermostat",
            "apply_mode": "set_temperature",
            "temperature_step": 0.5,
            "manual_override_guard": True,
            "override_branches": {
                "away": {
                    "branch": "fixed_target",
                    "target_temperature": 20.0,
                }
            },
        }
    }
    engine = _build_engine(
        options,
        {
            "climate.test_thermostat": ("heat", {"temperature": 18.0}),
        },
    )
    engine.state.set_binary("heima_heating_manual_hold", True)

    await engine.async_evaluate(reason="test")
    await engine.async_evaluate(reason="test-repeat")

    payloads = [payload for event_type, payload in engine._hass.bus.events if event_type == "heima_event"]
    blocked = [payload for payload in payloads if payload["type"] == "heating.manual_override_blocked"]
    assert len(blocked) == 1


def test_vacation_curve_without_required_bindings_is_inactive():
    options = _with_house_signal_binding(
        {
        "heating": {
            "climate_entity": "climate.test_thermostat",
            "apply_mode": "set_temperature",
            "temperature_step": 0.5,
            "manual_override_guard": True,
            "override_branches": {
                "vacation": {
                    "branch": "vacation_curve",
                    "vacation_ramp_down_h": 8.0,
                    "vacation_ramp_up_h": 10.0,
                    "vacation_min_temp": 16.5,
                    "vacation_comfort_temp": 19.5,
                    "vacation_min_total_hours_for_ramp": 24.0,
                }
            },
        }
    },
        vacation_mode="input_boolean.vacation_mode",
    )
    engine = _build_engine(
        options,
        {
            "input_boolean.vacation_mode": "on",
            "climate.test_thermostat": ("heat", {"temperature": 18.0}),
        },
    )

    snapshot = engine._compute_snapshot(reason="test")
    plan = engine._build_apply_plan(snapshot)

    assert snapshot.house_state == "vacation"
    assert engine.state.get_sensor("heima_heating_state") == "inactive"
    assert engine.state.get_sensor("heima_heating_reason") == "vacation_bindings_unavailable"
    assert engine.state.get_binary("heima_heating_applying_guard") is True
    assert not any(step.domain == "heating" for step in plan.steps)


@pytest.mark.asyncio
async def test_heating_runtime_emits_vacation_bindings_unavailable_event_once_per_transition():
    options = _with_house_signal_binding(
        {
        "heating": {
            "climate_entity": "climate.test_thermostat",
            "apply_mode": "set_temperature",
            "temperature_step": 0.5,
            "manual_override_guard": True,
            "override_branches": {
                "vacation": {
                    "branch": "vacation_curve",
                    "vacation_ramp_down_h": 8.0,
                    "vacation_ramp_up_h": 10.0,
                    "vacation_min_temp": 16.5,
                    "vacation_comfort_temp": 19.5,
                    "vacation_min_total_hours_for_ramp": 24.0,
                }
            },
        }
    },
        vacation_mode="input_boolean.vacation_mode",
    )
    engine = _build_engine(
        options,
        {
            "input_boolean.vacation_mode": "on",
            "climate.test_thermostat": ("heat", {"temperature": 18.0}),
        },
    )

    await engine.async_evaluate(reason="test")
    await engine.async_evaluate(reason="test-repeat")

    payloads = [payload for event_type, payload in engine._hass.bus.events if event_type == "heima_event"]
    unavailable = [payload for payload in payloads if payload["type"] == "heating.vacation_bindings_unavailable"]
    assert len(unavailable) == 1


@pytest.mark.asyncio
async def test_config_invalid_event_emitted_for_missing_climate_entity():
    options = {
        "heating": {
            "climate_entity": "climate.missing",
            "apply_mode": "set_temperature",
            "override_branches": {"home": {"branch": "fixed_target", "target_temperature": 20.0}},
        }
    }
    engine = _build_engine(options, {})  # climate.missing not in states

    await engine.async_evaluate(reason="test")
    payloads = [p for _, p in engine._hass.bus.events if p.get("type") == "system.config_invalid"]
    assert len(payloads) == 1
    assert any("climate.missing" in issue for issue in payloads[0]["context"]["issues"])


@pytest.mark.asyncio
async def test_config_invalid_event_emitted_once_until_fingerprint_changes():
    options = {
        "heating": {
            "climate_entity": "climate.missing",
            "apply_mode": "set_temperature",
            "override_branches": {},
        }
    }
    engine = _build_engine(options, {})

    await engine.async_evaluate(reason="test")
    await engine.async_evaluate(reason="test-repeat")
    payloads = [p for _, p in engine._hass.bus.events if p.get("type") == "system.config_invalid"]
    assert len(payloads) == 1  # deduped by fingerprint, not re-queued
