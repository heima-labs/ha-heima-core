from types import SimpleNamespace

import pytest
from homeassistant.exceptions import ServiceNotFound

from custom_components.heima.runtime.contracts import HeimaEvent
from custom_components.heima.runtime.domains.events import EventsDomain
from custom_components.heima.runtime.notifications import (
    AUDIENCE_POLICY_ADMINS,
    AUDIENCE_POLICY_ADMINS_AFTER_PERSISTENCE,
    AUDIENCE_POLICY_OBSERVABILITY,
    AUDIENCE_POLICY_RESIDENTS_AND_ADMINS,
    AUDIENCE_POLICY_SECURITY_CRITICAL_ELSE_ADMINS_AFTER_PERSISTENCE,
    ActionableNotification,
    HeimaEventPipeline,
    NotificationAction,
    NotificationDeliveryPolicy,
    normalize_notification_policy_config,
    parse_actionable_notification_response,
    render_notification_event,
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
            },
            "startup_notification_grace_s": 0,
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
            },
            "startup_notification_grace_s": 0,
        },
    )

    assert decision.outcome == "missing_audience_target"
    assert decision.push_policy == AUDIENCE_POLICY_ADMINS
    assert decision.target_roles == ("admins",)
    assert decision.route_targets == ()
    assert decision.reason == "missing_audience_target"


def test_notification_delivery_policy_startup_grace_suppresses_noncritical_push(monkeypatch):
    t = 100.0
    monkeypatch.setattr(
        "custom_components.heima.runtime.notifications.time.monotonic",
        lambda: t,
    )
    policy = NotificationDeliveryPolicy()

    decision = policy.decide(
        HeimaEvent(
            type="system.config_invalid",
            key="system.config_invalid",
            severity="warn",
            title="Heima configuration issue",
            message="Configuration issue detected.",
        ),
        {
            "audience_targets": {"admins": ["admins"], "residents": ["residents"]},
            "startup_notification_grace_s": 300,
        },
    )

    assert decision.outcome == "startup_grace"
    assert decision.reason == "startup_notification_grace_active"


def test_notification_delivery_policy_startup_grace_does_not_suppress_critical_security(
    monkeypatch,
):
    t = 100.0
    monkeypatch.setattr(
        "custom_components.heima.runtime.notifications.time.monotonic",
        lambda: t,
    )
    policy = NotificationDeliveryPolicy()

    decision = policy.decide(
        HeimaEvent(
            type="security.alarm_triggered",
            key="security.alarm_triggered",
            severity="critical",
            title="Alarm triggered",
            message="Alarm triggered.",
        ),
        {
            "audience_targets": {"admins": ["admins"], "residents": ["residents"]},
            "startup_notification_grace_s": 300,
        },
    )

    assert decision.outcome == "deliver"
    assert decision.security_critical is True


def test_render_reaction_notification_uses_label_and_hides_uuid_for_residents():
    reaction_uuid = "38f7e744-99cb-413f-9d12-60fdfc9570eb"

    rendered = render_notification_event(
        HeimaEvent(
            type="reaction.fired",
            key=f"reaction.fired.{reaction_uuid}",
            severity="info",
            title=f"Reaction fired: {reaction_uuid}",
            message=f"Reaction '{reaction_uuid}' produced 2 step(s).",
            context={
                "reaction_id": reaction_uuid,
                "reaction_label": "Evening studio lights",
            },
        ),
        audience="resident",
    )

    assert rendered.title == "Home automation ran"
    assert rendered.message == "Evening studio lights was applied."
    assert reaction_uuid not in rendered.title
    assert reaction_uuid not in rendered.message


def test_render_people_notification_uses_display_name():
    rendered = render_notification_event(
        HeimaEvent(
            type="people.arrive",
            key="people.arrive.stefano",
            severity="info",
            title="Person arrived",
            message="Person 'stefano' arrived.",
            context={"person": "stefano", "display_name": "Stefano"},
        ),
        audience="resident",
    )

    assert rendered.title == "Person arrived"
    assert rendered.message == "Stefano arrived home."


def test_render_admin_system_notification_keeps_readable_summary_and_event_type():
    rendered = render_notification_event(
        HeimaEvent(
            type="system.config_invalid",
            key="system.config_invalid",
            severity="warn",
            title="Heima configuration issue",
            message="2 configuration issue(s) detected.",
        ),
        audience="admin",
    )

    assert rendered.title == "Heima configuration issue"
    assert rendered.message.startswith("2 configuration issue(s) detected.")
    assert "system.config_invalid" in rendered.message


@pytest.mark.asyncio
async def test_events_domain_observability_only_event_still_fires_bus_without_push():
    bus = _FakeBus()
    services = _FakeServices(available={"mobile_app_resident": object()})
    hass = SimpleNamespace(bus=bus, services=services)
    events = EventsDomain(hass)

    emitted = await events.async_emit_event_obj(
        HeimaEvent(
            type="people.arrive",
            key="people.arrive.stefano",
            severity="info",
            title="Person arrived",
            message="Person arrived.",
        ),
        notifications_config={
            "recipients": {"resident": ["mobile_app_resident"]},
            "recipient_groups": {"residents": ["resident"]},
            "route_targets": ["residents"],
        },
    )

    assert bool(emitted) is True
    assert len(bus.events) == 1
    assert services.calls == []
    assert events.pipeline.stats.emitted == 1
    policy_diag = events.diagnostics()["notification_delivery_policy"]
    assert policy_diag["decision_counts"]["observability_only"] == 1
    assert policy_diag["recent_decisions"][-1]["reason"] == "policy_observability_only"
    assert policy_diag["recent_decisions"][-1]["event_family"] == "people"


@pytest.mark.asyncio
async def test_events_domain_system_event_is_observable_without_unconditional_push():
    bus = _FakeBus()
    services = _FakeServices(available={"mobile_app_resident": object()})
    hass = SimpleNamespace(bus=bus, services=services)
    events = EventsDomain(hass)

    emitted = await events.async_emit_event_obj(
        HeimaEvent(
            type="system.config_invalid",
            key="system.config_invalid",
            severity="warn",
            title="Heima configuration issue",
            message="Configuration issue detected.",
        ),
        notifications_config={
            "recipients": {"resident": ["mobile_app_resident"]},
            "recipient_groups": {"residents": ["resident"]},
            "route_targets": ["residents"],
            "audience_targets": {"admins": [], "residents": ["residents"]},
            "startup_notification_grace_s": 0,
        },
    )

    assert bool(emitted) is True
    assert len(bus.events) == 1
    assert services.calls == []
    assert events.pipeline.stats.emitted == 1


@pytest.mark.asyncio
async def test_events_domain_legacy_route_targets_do_not_receive_noisy_categories_by_default():
    bus = _FakeBus()
    services = _FakeServices(available={"mobile_app_resident": object()})
    hass = SimpleNamespace(bus=bus, services=services)
    events = EventsDomain(hass)

    await events.async_emit_event_obj(
        HeimaEvent(
            type="reaction.fired",
            key="reaction.fired.scene",
            severity="info",
            title="Reaction fired",
            message="Reaction produced steps.",
        ),
        notifications_config={
            "recipients": {"resident": ["mobile_app_resident"]},
            "recipient_groups": {"residents": ["resident"]},
            "route_targets": ["residents"],
        },
    )

    assert len(bus.events) == 1
    assert services.calls == []


@pytest.mark.asyncio
async def test_events_domain_security_critical_uses_audience_targets_for_push():
    bus = _FakeBus()
    services = _FakeServices(
        available={
            "mobile_app_resident": object(),
            "mobile_app_admin": object(),
        }
    )
    hass = SimpleNamespace(bus=bus, services=services)
    events = EventsDomain(hass)

    await events.async_emit_event_obj(
        HeimaEvent(
            type="security.alarm_triggered",
            key="security.alarm_triggered",
            severity="critical",
            title="Alarm triggered",
            message="Alarm triggered.",
        ),
        notifications_config={
            "recipients": {
                "resident": ["mobile_app_resident"],
                "admin": ["mobile_app_admin"],
            },
            "recipient_groups": {
                "residents": ["resident"],
                "admins": ["admin"],
            },
            "route_targets": [],
            "startup_notification_grace_s": 0,
        },
    )

    called_services = [
        service for domain, service, _data, _blocking in services.calls if domain == "notify"
    ]
    assert called_services == ["mobile_app_resident", "mobile_app_admin"]


@pytest.mark.asyncio
async def test_events_domain_reaction_push_uses_resident_safe_rendered_payload():
    reaction_uuid = "38f7e744-99cb-413f-9d12-60fdfc9570eb"
    bus = _FakeBus()
    services = _FakeServices(available={"mobile_app_resident": object()})
    hass = SimpleNamespace(bus=bus, services=services)
    events = EventsDomain(hass)

    await events.async_emit_event_obj(
        HeimaEvent(
            type="reaction.fired",
            key=f"reaction.fired.{reaction_uuid}",
            severity="info",
            title=f"Reaction fired: {reaction_uuid}",
            message=f"Reaction '{reaction_uuid}' produced 2 step(s).",
            context={
                "reaction_id": reaction_uuid,
                "reaction_label": "Evening studio lights",
            },
        ),
        notifications_config={
            "recipients": {"resident": ["mobile_app_resident"]},
            "recipient_groups": {"residents": ["resident"]},
            "enabled_event_categories": ["reaction"],
            "audience_policy": {"reaction": {"push": "residents"}},
            "startup_notification_grace_s": 0,
        },
    )

    notify_calls = [c for c in services.calls if c[0] == "notify"]
    assert len(notify_calls) == 1
    payload = notify_calls[0][2]
    assert payload["title"] == "Home automation ran"
    assert payload["message"] == "Evening studio lights was applied."
    assert reaction_uuid not in payload["title"]
    assert reaction_uuid not in payload["message"]


@pytest.mark.asyncio
async def test_events_domain_occupancy_mismatch_before_persistence_has_no_push(monkeypatch):
    bus = _FakeBus()
    services = _FakeServices(available={"mobile_app_admin": object()})
    hass = SimpleNamespace(bus=bus, services=services)
    events = EventsDomain(hass)

    t = 100.0
    monkeypatch.setattr(
        "custom_components.heima.runtime.notifications.time.monotonic",
        lambda: t,
    )

    await events.async_emit_event_obj(
        HeimaEvent(
            type="occupancy.inconsistency",
            key="occupancy.inconsistency.presence_without_room",
            severity="warn",
            title="Occupancy inconsistency",
            message="Presence says someone is home, but no room is occupied.",
        ),
        notifications_config={
            "recipients": {"admin": ["mobile_app_admin"]},
            "recipient_groups": {"admins": ["admin"]},
            "persistence_thresholds": {"occupancy_mismatch": 600},
            "startup_notification_grace_s": 0,
        },
    )

    assert len(bus.events) == 1
    assert services.calls == []


@pytest.mark.asyncio
async def test_events_domain_persistent_occupancy_mismatch_sends_one_admin_push(monkeypatch):
    bus = _FakeBus()
    services = _FakeServices(available={"mobile_app_admin": object()})
    hass = SimpleNamespace(bus=bus, services=services)
    events = EventsDomain(hass)

    t = 100.0
    monkeypatch.setattr(
        "custom_components.heima.runtime.notifications.time.monotonic",
        lambda: t,
    )
    event = HeimaEvent(
        type="occupancy.inconsistency",
        key="occupancy.inconsistency.presence_without_room",
        severity="warn",
        title="Occupancy inconsistency",
        message="Presence says someone is home, but no room is occupied.",
    )
    config = {
        "recipients": {"admin": ["mobile_app_admin"]},
        "recipient_groups": {"admins": ["admin"]},
        "persistence_thresholds": {"occupancy_mismatch": 600},
        "startup_notification_grace_s": 0,
    }

    await events.async_emit_event_obj(event, notifications_config=config)
    t = 701.0
    await events.async_emit_event_obj(event, notifications_config=config)
    t = 702.0
    await events.async_emit_event_obj(event, notifications_config=config)

    notify_calls = [c for c in services.calls if c[0] == "notify"]
    assert len(bus.events) == 3
    assert len(notify_calls) == 1
    assert notify_calls[0][1] == "mobile_app_admin"


@pytest.mark.asyncio
async def test_events_domain_persistence_resets_after_quiet_period(monkeypatch):
    bus = _FakeBus()
    services = _FakeServices(available={"mobile_app_admin": object()})
    hass = SimpleNamespace(bus=bus, services=services)
    events = EventsDomain(hass)

    t = 100.0
    monkeypatch.setattr(
        "custom_components.heima.runtime.notifications.time.monotonic",
        lambda: t,
    )
    event = HeimaEvent(
        type="occupancy.inconsistency",
        key="occupancy.inconsistency.presence_without_room",
        severity="warn",
        title="Occupancy inconsistency",
        message="Presence says someone is home, but no room is occupied.",
    )
    config = {
        "recipients": {"admin": ["mobile_app_admin"]},
        "recipient_groups": {"admins": ["admin"]},
        "persistence_thresholds": {"occupancy_mismatch": 10},
        "aggregation": {
            "mismatch_window_s": 0,
            "global_burst_limit": {"max_notifications": 10, "window_s": 60},
        },
        "dedup_window_s": 0,
        "rate_limit_per_key_s": 0,
        "startup_notification_grace_s": 0,
    }

    await events.async_emit_event_obj(event, notifications_config=config)
    t = 111.0
    await events.async_emit_event_obj(event, notifications_config=config)
    t = 112.0
    await events.async_emit_event_obj(event, notifications_config=config)
    t = 130.0
    await events.async_emit_event_obj(event, notifications_config=config)
    t = 141.0
    await events.async_emit_event_obj(event, notifications_config=config)

    notify_calls = [c for c in services.calls if c[0] == "notify"]
    assert len(notify_calls) == 2
    policy_diag = events.diagnostics()["notification_delivery_policy"]
    outcomes = [row["outcome"] for row in policy_diag["recent_decisions"]]
    assert outcomes == [
        "waiting_persistence",
        "deliver",
        "suppressed_aggregation",
        "waiting_persistence",
        "deliver",
    ]


@pytest.mark.asyncio
async def test_events_domain_people_push_aggregation_prevents_arrival_storm(monkeypatch):
    bus = _FakeBus()
    services = _FakeServices(available={"mobile_app_resident": object()})
    hass = SimpleNamespace(bus=bus, services=services)
    events = EventsDomain(hass)

    t = 100.0
    monkeypatch.setattr(
        "custom_components.heima.runtime.notifications.time.monotonic",
        lambda: t,
    )
    config = {
        "recipients": {"resident": ["mobile_app_resident"]},
        "recipient_groups": {"residents": ["resident"]},
        "audience_policy": {"people": {"push": "residents"}},
        "startup_notification_grace_s": 0,
    }

    for person in ("stefano", "antonia", "guest"):
        await events.async_emit_event_obj(
            HeimaEvent(
                type="people.arrive",
                key=f"people.arrive.{person}",
                severity="info",
                title="Person arrived",
                message=f"Person '{person}' arrived.",
            ),
            notifications_config=config,
        )
        t += 1.0

    notify_calls = [c for c in services.calls if c[0] == "notify"]
    assert len(bus.events) == 3
    assert len(notify_calls) == 1


@pytest.mark.asyncio
async def test_events_domain_people_aggregation_does_not_suppress_mismatch(monkeypatch):
    bus = _FakeBus()
    services = _FakeServices(
        available={
            "mobile_app_resident": object(),
            "mobile_app_admin": object(),
        }
    )
    hass = SimpleNamespace(bus=bus, services=services)
    events = EventsDomain(hass)

    t = 100.0
    monkeypatch.setattr(
        "custom_components.heima.runtime.notifications.time.monotonic",
        lambda: t,
    )
    config = {
        "recipients": {
            "resident": ["mobile_app_resident"],
            "admin": ["mobile_app_admin"],
        },
        "recipient_groups": {
            "residents": ["resident"],
            "admins": ["admin"],
        },
        "audience_policy": {
            "people": {"push": "residents"},
            "occupancy_mismatch": {"push": "admins"},
        },
        "aggregation": {
            "presence_transition_window_s": 120,
            "mismatch_window_s": 300,
            "global_burst_limit": {"max_notifications": 10, "window_s": 60},
        },
        "startup_notification_grace_s": 0,
    }

    await events.async_emit_event_obj(
        HeimaEvent(
            type="people.arrive",
            key="people.arrive.stefano",
            severity="info",
            title="Person arrived",
            message="Person arrived.",
        ),
        notifications_config=config,
    )
    t = 101.0
    await events.async_emit_event_obj(
        HeimaEvent(
            type="occupancy.inconsistency",
            key="occupancy.inconsistency.presence_without_room",
            severity="warn",
            title="Occupancy inconsistency",
            message="Presence says someone is home, but no room is occupied.",
        ),
        notifications_config=config,
    )

    called_services = [
        service for domain, service, _data, _blocking in services.calls if domain == "notify"
    ]
    assert called_services == ["mobile_app_resident", "mobile_app_admin"]


@pytest.mark.asyncio
async def test_events_domain_global_burst_limit_does_not_limit_event_bus(monkeypatch):
    bus = _FakeBus()
    services = _FakeServices(
        available={
            "mobile_app_admin": object(),
            "mobile_app_resident": object(),
        }
    )
    hass = SimpleNamespace(bus=bus, services=services)
    events = EventsDomain(hass)

    t = 100.0
    monkeypatch.setattr(
        "custom_components.heima.runtime.notifications.time.monotonic",
        lambda: t,
    )
    config = {
        "recipients": {
            "admin": ["mobile_app_admin"],
            "resident": ["mobile_app_resident"],
        },
        "recipient_groups": {
            "admins": ["admin"],
            "residents": ["resident"],
        },
        "aggregation": {"global_burst_limit": {"max_notifications": 2, "window_s": 60}},
        "startup_notification_grace_s": 0,
    }

    for idx in range(3):
        await events.async_emit_event_obj(
            HeimaEvent(
                type="system.config_invalid",
                key=f"system.config_invalid.{idx}",
                severity="warn",
                title="Heima configuration issue",
                message="Configuration issue detected.",
            ),
            notifications_config=config,
        )
        t += 1.0

    await events.async_emit_event_obj(
        HeimaEvent(
            type="security.alarm_triggered",
            key="security.alarm_triggered",
            severity="critical",
            title="Alarm triggered",
            message="Alarm triggered.",
        ),
        notifications_config=config,
    )

    called_services = [
        service for domain, service, _data, _blocking in services.calls if domain == "notify"
    ]
    assert len(bus.events) == 4
    assert called_services == [
        "mobile_app_admin",
        "mobile_app_admin",
        "mobile_app_resident",
        "mobile_app_admin",
    ]


@pytest.mark.asyncio
async def test_events_domain_records_delivery_deferred_without_burst_state(monkeypatch):
    bus = _FakeBus()
    services = _FakeServices(available={})
    hass = SimpleNamespace(bus=bus, services=services)
    events = EventsDomain(hass)

    t = 100.0
    monkeypatch.setattr(
        "custom_components.heima.runtime.notifications.time.monotonic",
        lambda: t,
    )
    config = {
        "recipients": {"admin": ["mobile_app_admin"]},
        "recipient_groups": {"admins": ["admin"]},
        "startup_notification_grace_s": 0,
    }

    await events.async_emit_event_obj(
        HeimaEvent(
            type="system.config_invalid",
            key="system.config_invalid",
            severity="warn",
            title="Heima configuration issue",
            message="Configuration issue detected.",
        ),
        notifications_config=config,
    )

    policy_diag = events.diagnostics()["notification_delivery_policy"]
    assert policy_diag["recent_decisions"][-1]["outcome"] == "delivery_deferred"
    assert policy_diag["burst"]["recent_delivery_count"] == 0


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
    assert bool(emitted) is True
    assert emitted.dropped_dedup is False
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
    assert bool(emitted) is True
    assert emitted.dropped_dedup is True
    assert pipeline.stats.dropped_dedup == 1
    assert len(bus.events) == 2


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
            assert bool(emitted) is True
        else:
            assert bool(emitted) is True

    assert pipeline.stats.dropped_rate_limited == 1
    assert len(bus.events) == 2


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

    assert bool(emitted) is True
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
