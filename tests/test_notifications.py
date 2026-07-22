from types import SimpleNamespace

import pytest
from homeassistant.exceptions import ServiceNotFound

from custom_components.heima.runtime.contracts import HeimaEvent
from custom_components.heima.runtime.notifications import (
    ActionableNotification,
    AUDIENCE_POLICY_ADMINS,
    AUDIENCE_POLICY_ADMINS_AFTER_PERSISTENCE,
    AUDIENCE_POLICY_OBSERVABILITY,
    AUDIENCE_POLICY_SECURITY_CRITICAL_ELSE_ADMINS_AFTER_PERSISTENCE,
    AUDIENCE_POLICY_RESIDENTS_AND_ADMINS,
    HeimaEventPipeline,
    NotificationAction,
    NotificationDeliveryPolicy,
    normalize_notification_policy_config,
    parse_actionable_notification_response,
)


class _FakeBus:
    def __init__(self):
        self.events = []

    def async_fire(self, event_type, data):
        self.events.append((event_type, data))


class _FakeServices:
    def __init__(
        self, available: dict[str, object] | None = None, fail_once: set[str] | None = None
    ):
        self.calls = []
        self.available = dict(available or {})
        self.fail_once = set(fail_once or set())

    async def async_call(self, domain, service, data, blocking=False):
        if domain == "notify" and service in self.fail_once:
            self.fail_once.remove(service)
            raise ServiceNotFound(domain, service)
        self.calls.append((domain, service, data, blocking))

    def async_services(self):
        return {"notify": dict(self.available)}


def test_notification_policy_defaults_are_materialized():
    config = normalize_notification_policy_config({})

    assert config["audience_targets"] == {
        "admins": ["admins"],
        "residents": ["residents"],
    }
    assert config["audience_policy"]["people"]["push"] == AUDIENCE_POLICY_OBSERVABILITY
    assert config["audience_policy"]["reaction"]["push"] == AUDIENCE_POLICY_OBSERVABILITY
    assert (
        config["audience_policy"]["occupancy_mismatch"]["push"]
        == AUDIENCE_POLICY_ADMINS_AFTER_PERSISTENCE
    )
    assert (
        config["audience_policy"]["security_presence_mismatch"]["push"]
        == AUDIENCE_POLICY_SECURITY_CRITICAL_ELSE_ADMINS_AFTER_PERSISTENCE
    )
    assert config["startup_notification_grace_s"] == 300
    assert config["persistence_thresholds"]["occupancy_mismatch"] == 600
    assert config["aggregation"]["global_burst_limit"] == {
        "max_notifications": 2,
        "window_s": 60,
    }


def test_notification_policy_preserves_partial_explicit_values():
    config = normalize_notification_policy_config(
        {
            "audience_targets": {"admins": ["stefano"]},
            "audience_policy": {"system_config_issue": {"push": AUDIENCE_POLICY_ADMINS}},
            "startup_notification_grace_s": 42,
            "persistence_thresholds": {"occupancy_mismatch": 123},
            "aggregation": {"global_burst_limit": {"max_notifications": 4}},
        }
    )

    assert config["audience_targets"]["admins"] == ["stefano"]
    assert config["audience_targets"]["residents"] == ["residents"]
    assert config["audience_policy"]["system_config_issue"]["push"] == AUDIENCE_POLICY_ADMINS
    assert config["audience_policy"]["people"]["push"] == AUDIENCE_POLICY_OBSERVABILITY
    assert config["startup_notification_grace_s"] == 42
    assert config["persistence_thresholds"]["occupancy_mismatch"] == 123
    assert config["persistence_thresholds"]["security_presence_mismatch"] == 300
    assert config["aggregation"]["global_burst_limit"] == {
        "max_notifications": 4,
        "window_s": 60,
    }


def test_notification_policy_sanitizes_invalid_values_deterministically():
    config = normalize_notification_policy_config(
        {
            "recipients": {"stefano": ["mobile_app_stefano"]},
            "recipient_groups": {"admins": ["stefano"]},
            "audience_targets": {
                "admins": ["admins", "observability", "missing"],
                "residents": ["missing"],
            },
            "audience_policy": {
                "people": {"push": "notify.mobile_app_stefano"},
                "system_config_issue": {"push": AUDIENCE_POLICY_ADMINS},
            },
            "startup_notification_grace_s": -1,
            "persistence_thresholds": {"occupancy_mismatch": "bad"},
            "aggregation": {"global_burst_limit": {"window_s": -10}},
        },
        sanitize_unresolved_targets=True,
    )

    assert config["audience_targets"] == {"admins": ["admins"], "residents": []}
    assert config["audience_policy"]["people"]["push"] == AUDIENCE_POLICY_OBSERVABILITY
    assert config["startup_notification_grace_s"] == 0
    assert config["persistence_thresholds"]["occupancy_mismatch"] == 600
    assert config["aggregation"]["global_burst_limit"]["window_s"] == 0


def test_notification_delivery_policy_people_arrive_is_observability_only_by_default():
    decision = NotificationDeliveryPolicy().decide(
        HeimaEvent(
            type="people.arrive",
            key="people.arrive.stefano",
            severity="info",
            title="Person arrived",
            message="Person 'stefano' arrived.",
        ),
        {},
    )

    assert decision.outcome == "observability_only"
    assert decision.event_family == "people"
    assert decision.push_policy == AUDIENCE_POLICY_OBSERVABILITY
    assert decision.route_targets == ()


def test_notification_delivery_policy_reaction_fired_is_observability_only_by_default():
    decision = NotificationDeliveryPolicy().decide(
        HeimaEvent(
            type="reaction.fired",
            key="reaction.fired.scene",
            severity="info",
            title="Reaction fired",
            message="Reaction produced steps.",
        ),
        {},
    )

    assert decision.outcome == "observability_only"
    assert decision.event_family == "reaction"
    assert decision.push_policy == AUDIENCE_POLICY_OBSERVABILITY


def test_notification_delivery_policy_system_config_issue_targets_admins_by_default():
    decision = NotificationDeliveryPolicy().decide(
        HeimaEvent(
            type="system.config_invalid",
            key="system.config_invalid",
            severity="warn",
            title="Heima configuration issue",
            message="Configuration issue detected.",
        ),
        {
            "audience_targets": {
                "admins": ["stefano_admins"],
                "residents": ["residents"],
            }
        },
    )

    assert decision.outcome == "deliver"
    assert decision.event_family == "system_config_issue"
    assert decision.push_policy == AUDIENCE_POLICY_ADMINS
    assert decision.target_roles == ("admins",)
    assert decision.route_targets == ("stefano_admins",)


def test_notification_delivery_policy_alarm_triggered_targets_residents_and_admins():
    decision = NotificationDeliveryPolicy().decide(
        HeimaEvent(
            type="security.alarm_triggered",
            key="security.alarm_triggered",
            severity="critical",
            title="Alarm triggered",
            message="Alarm triggered.",
        ),
        {
            "audience_targets": {
                "admins": ["admins"],
                "residents": ["residents"],
            }
        },
    )

    assert decision.outcome == "deliver"
    assert decision.event_family == "security_critical"
    assert decision.push_policy == AUDIENCE_POLICY_RESIDENTS_AND_ADMINS
    assert decision.target_roles == ("residents", "admins")
    assert decision.route_targets == ("residents", "admins")
    assert decision.security_critical is True


def test_notification_delivery_policy_armed_away_home_targets_residents_and_admins():
    decision = NotificationDeliveryPolicy().decide(
        HeimaEvent(
            type="security.armed_away_but_home",
            key="security.armed_away_but_home",
            severity="warn",
            title="Security inconsistency",
            message="Security is armed away while someone is home.",
            context={"security_state": "armed_away", "people_home_list": ["stefano"]},
        ),
        {
            "audience_targets": {
                "admins": ["admins"],
                "residents": ["residents"],
            }
        },
    )

    assert decision.outcome == "deliver"
    assert decision.push_policy == AUDIENCE_POLICY_RESIDENTS_AND_ADMINS
    assert decision.route_targets == ("residents", "admins")
    assert decision.security_critical is True


def test_notification_delivery_policy_missing_admin_target_has_no_resident_fallback():
    decision = NotificationDeliveryPolicy().decide(
        HeimaEvent(
            type="system.config_invalid",
            key="system.config_invalid",
            severity="warn",
            title="Heima configuration issue",
            message="Configuration issue detected.",
        ),
        {
            "audience_targets": {
                "admins": [],
                "residents": ["residents"],
            }
        },
    )

    assert decision.outcome == "missing_audience_target"
    assert decision.push_policy == AUDIENCE_POLICY_ADMINS
    assert decision.target_roles == ("admins",)
    assert decision.route_targets == ()
    assert decision.reason == "missing_audience_target"


@pytest.mark.asyncio
async def test_event_pipeline_deduplicates(monkeypatch):
    bus = _FakeBus()
    services = _FakeServices()
    hass = SimpleNamespace(bus=bus, services=services)
    pipeline = HeimaEventPipeline(hass)

    t = 100.0
    monkeypatch.setattr(
        "custom_components.heima.runtime.notifications.time.monotonic",
        lambda: t,
    )

    event = HeimaEvent(
        type="lighting.scene_missing",
        key="lighting.scene_missing.room1.scene_relax",
        severity="warn",
        title="x",
        message="x",
    )
    emitted = await pipeline.async_emit(
        event,
        routes=[],
        dedup_window_s=60,
        rate_limit_per_key_s=300,
    )
    assert emitted is True
    assert len(bus.events) == 1

    t = 110.0
    emitted = await pipeline.async_emit(
        HeimaEvent(
            type=event.type,
            key=event.key,
            severity=event.severity,
            title=event.title,
            message=event.message,
        ),
        routes=[],
        dedup_window_s=60,
        rate_limit_per_key_s=300,
    )
    assert emitted is False
    assert pipeline.stats.dropped_dedup == 1
    assert len(bus.events) == 1


@pytest.mark.asyncio
async def test_event_pipeline_rate_limits_after_dedup_window(monkeypatch):
    bus = _FakeBus()
    services = _FakeServices()
    hass = SimpleNamespace(bus=bus, services=services)
    pipeline = HeimaEventPipeline(hass)

    t = 100.0
    monkeypatch.setattr(
        "custom_components.heima.runtime.notifications.time.monotonic",
        lambda: t,
    )

    key = "lighting.hold.room1"
    for current_t in (100.0, 170.0):
        t = current_t
        emitted = await pipeline.async_emit(
            HeimaEvent(
                type="lighting.hold_on",
                key=key,
                severity="info",
                title="hold",
                message="hold",
            ),
            routes=[],
            dedup_window_s=60,
            rate_limit_per_key_s=300,
        )
        if current_t == 100.0:
            assert emitted is True
        else:
            assert emitted is False

    assert pipeline.stats.dropped_rate_limited == 1
    assert len(bus.events) == 1


@pytest.mark.asyncio
async def test_event_pipeline_defers_missing_notify_route_without_failing():
    bus = _FakeBus()
    services = _FakeServices(available={})
    hass = SimpleNamespace(bus=bus, services=services)
    pipeline = HeimaEventPipeline(hass)

    emitted = await pipeline.async_emit(
        HeimaEvent(
            type="debug.test",
            key="debug.test",
            severity="info",
            title="t",
            message="m",
        ),
        routes=["mobile_app_test"],
        dedup_window_s=0,
        rate_limit_per_key_s=0,
    )

    assert emitted is True
    assert len(bus.events) == 1
    assert services.calls == []
    assert pipeline.stats.notify_route_unavailable >= 1


@pytest.mark.asyncio
async def test_event_pipeline_retries_deferred_route_when_service_appears():
    bus = _FakeBus()
    services = _FakeServices(available={})
    hass = SimpleNamespace(bus=bus, services=services)
    pipeline = HeimaEventPipeline(hass)

    first = HeimaEvent(
        type="debug.first",
        key="debug.first",
        severity="info",
        title="first",
        message="first",
    )
    await pipeline.async_emit(
        first,
        routes=["mobile_app_test"],
        dedup_window_s=0,
        rate_limit_per_key_s=0,
    )
    assert services.calls == []

    services.available["mobile_app_test"] = object()
    second = HeimaEvent(
        type="debug.second",
        key="debug.second",
        severity="info",
        title="second",
        message="second",
    )
    await pipeline.async_emit(
        second,
        routes=[],
        dedup_window_s=0,
        rate_limit_per_key_s=0,
    )

    notify_calls = [c for c in services.calls if c[0] == "notify" and c[1] == "mobile_app_test"]
    assert len(notify_calls) == 1
    assert notify_calls[0][2]["title"] == "first"
    assert pipeline.stats.notify_route_retried == 1


@pytest.mark.asyncio
async def test_event_pipeline_resolves_recipient_aliases_and_groups():
    bus = _FakeBus()
    services = _FakeServices(
        available={
            "mobile_app_phone_stefano": object(),
            "mobile_app_mac_stefano": object(),
            "mobile_app_laura": object(),
            "mobile_app_legacy": object(),
        }
    )
    hass = SimpleNamespace(bus=bus, services=services)
    pipeline = HeimaEventPipeline(hass)

    await pipeline.async_emit(
        HeimaEvent(
            type="debug.targets",
            key="debug.targets",
            severity="info",
            title="Targets",
            message="targets",
        ),
        routes=["mobile_app_legacy"],
        recipients={
            "stefano": ["mobile_app_phone_stefano", "mobile_app_mac_stefano"],
            "laura": ["mobile_app_laura"],
        },
        recipient_groups={"family": ["stefano", "laura"]},
        route_targets=["family", "stefano", "missing"],
        dedup_window_s=0,
        rate_limit_per_key_s=0,
    )

    called_services = [
        service for domain, service, _data, _blocking in services.calls if domain == "notify"
    ]
    assert called_services == [
        "mobile_app_legacy",
        "mobile_app_phone_stefano",
        "mobile_app_mac_stefano",
        "mobile_app_laura",
    ]
    assert pipeline.stats.notify_target_resolution_errors == 1


@pytest.mark.asyncio
async def test_actionable_notification_filters_non_actionable_routes():
    bus = _FakeBus()
    services = _FakeServices(
        available={
            "mobile_app_phone_stefano": object(),
            "mobile_app_mac_stefano": object(),
            "mobile_app_laura": object(),
        }
    )
    hass = SimpleNamespace(bus=bus, services=services)
    pipeline = HeimaEventPipeline(hass)

    result = await pipeline.async_send_actionable(
        ActionableNotification(
            title="Apply scene?",
            message="Apply the Studio scene.",
            request_id="request-1",
            actions=(
                NotificationAction("heima.runtime_request.approve", "Apply"),
                NotificationAction("heima.runtime_request.dismiss", "Skip"),
            ),
        ),
        recipients={
            "stefano": ["mobile_app_phone_stefano", "mobile_app_mac_stefano"],
            "laura": ["mobile_app_laura"],
        },
        recipient_groups={"family": ["stefano", "laura"]},
        route_targets=["family"],
        notification_service_capabilities={
            "mobile_app_phone_stefano": {"supports_actions": True},
            "mobile_app_mac_stefano": {"supports_actions": False},
        },
    )

    assert result.delivered_routes == ("mobile_app_phone_stefano",)
    assert result.skipped_non_actionable_routes == (
        "mobile_app_mac_stefano",
        "mobile_app_laura",
    )
    assert result.failure_reason == ""
    assert pipeline.stats.notify_actionable_delivered == 1
    assert services.calls == [
        (
            "notify",
            "mobile_app_phone_stefano",
            {
                "title": "Apply scene?",
                "message": "Apply the Studio scene.",
                "data": {
                    "tag": "request-1",
                    "category": "runtime_confirmation",
                    "action_data": {"request_id": "request-1"},
                    "actions": [
                        {
                            "action": "heima.runtime_request.approve",
                            "title": "Apply",
                        },
                        {
                            "action": "heima.runtime_request.dismiss",
                            "title": "Skip",
                        },
                    ],
                },
            },
            True,
        )
    ]


@pytest.mark.asyncio
async def test_actionable_notification_fails_closed_without_actionable_route():
    bus = _FakeBus()
    services = _FakeServices(available={"mobile_app_phone_stefano": object()})
    hass = SimpleNamespace(bus=bus, services=services)
    pipeline = HeimaEventPipeline(hass)

    result = await pipeline.async_send_actionable(
        ActionableNotification(
            title="Apply scene?",
            message="Apply the Studio scene.",
            request_id="request-1",
            actions=(NotificationAction("approve", "Apply"),),
        ),
        recipients={"stefano": ["mobile_app_phone_stefano"]},
        route_targets=["stefano"],
        notification_service_capabilities={"mobile_app_phone_stefano": {"supports_actions": False}},
    )

    assert result.delivered is False
    assert result.failure_reason == "no_actionable_route"
    assert result.skipped_non_actionable_routes == ("mobile_app_phone_stefano",)
    assert services.calls == []
    assert pipeline.stats.notify_actionable_no_route == 1


def test_parse_actionable_notification_response_prefers_action_data_request_id():
    response = parse_actionable_notification_response(
        {
            "action": "heima.runtime_request.approve",
            "tag": "fallback-request",
            "action_data": {"request_id": "request-1"},
        }
    )

    assert response is not None
    assert response.action_id == "heima.runtime_request.approve"
    assert response.request_id == "request-1"


def test_parse_actionable_notification_response_uses_android_tag_fallback():
    response = parse_actionable_notification_response(
        {
            "action": "heima.runtime_request.dismiss",
            "tag": "request-1",
        }
    )

    assert response is not None
    assert response.action_id == "heima.runtime_request.dismiss"
    assert response.request_id == "request-1"


def test_parse_actionable_notification_response_rejects_missing_request_id():
    assert (
        parse_actionable_notification_response({"action": "heima.runtime_request.approve"}) is None
    )
