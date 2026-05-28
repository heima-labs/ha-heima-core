"""Tests for Phase V signal discovery inventory classification."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.heima.const import (
    SIGNAL_DISCOVERY_ANALYZER_ID,
    SIGNAL_DISCOVERY_REACTION_TYPE,
)
from custom_components.heima.coordinator import HeimaCoordinator
from custom_components.heima.runtime.analyzers.base import ReactionProposal
from custom_components.heima.runtime.signal_discovery import (
    HAEntityDescriptor,
    SignalDiscoveryAudit,
    SignalOptionsPatch,
    apply_signal_options_patch,
)


def _entity(
    entity_id: str,
    *,
    domain: str = "sensor",
    device_class: str | None = "illuminance",
    unit: str | None = None,
    area_name: str | None = "Studio",
) -> HAEntityDescriptor:
    return HAEntityDescriptor(
        entity_id=entity_id,
        domain=domain,
        device_class=device_class,
        unit_of_measurement=unit,
        area_id="area_studio" if area_name else None,
        area_name=area_name,
        current_state="on",
    )


def test_signal_discovery_classifies_illuminance_room_signal() -> None:
    suggestions = SignalDiscoveryAudit().run(
        [
            _entity(
                "sensor.studio_lux",
                device_class="illuminance",
                unit="lx",
            )
        ],
        [{"room_id": "studio"}],
    )

    assert len(suggestions) == 1
    suggestion = suggestions[0]
    assert suggestion.entity_id == "sensor.studio_lux"
    assert suggestion.room_id == "studio"
    assert suggestion.role == "room_signal"
    assert suggestion.signal_name == "room_lux"
    assert suggestion.device_class == "illuminance"
    assert suggestion.confidence == 0.95
    assert suggestion.identity_key == "signal_discovery:sensor.studio_lux"
    assert suggestion.suggestion_id
    assert suggestion.options_patch.room_id == "studio"
    assert suggestion.options_patch.role == "room_signal"
    assert suggestion.options_patch.payload == {
        "signal_name": "room_lux",
        "entity_id": "sensor.studio_lux",
        "device_class": "illuminance",
        "buckets": [
            {"label": "dark", "upper_bound": 30},
            {"label": "dim", "upper_bound": 100},
            {"label": "ok", "upper_bound": 300},
            {"label": "bright", "upper_bound": None},
        ],
    }
    assert "device_class=illuminance" in suggestion.evidence
    assert "unit=lx" in suggestion.evidence
    assert "matched room: studio (area: Studio)" in suggestion.evidence


def test_signal_discovery_classifies_co2_and_humidity_buckets() -> None:
    suggestions = SignalDiscoveryAudit().run(
        [
            _entity("sensor.bathroom_humidity", device_class="humidity", area_name="Bagno"),
            _entity("sensor.studio_co2", device_class="carbon_dioxide", area_name="Studio"),
        ],
        [{"room_id": "studio"}, {"room_id": "bagno"}],
    )

    by_signal = {suggestion.signal_name: suggestion for suggestion in suggestions}
    assert by_signal["room_co2"].options_patch.payload["buckets"] == [
        {"label": "ok", "upper_bound": 800},
        {"label": "elevated", "upper_bound": 1200},
        {"label": "high", "upper_bound": None},
    ]
    assert by_signal["room_humidity"].options_patch.payload["buckets"] == [
        {"label": "low", "upper_bound": 40},
        {"label": "ok", "upper_bound": 70},
        {"label": "high", "upper_bound": None},
    ]
    assert by_signal["room_humidity"].confidence == 0.90


def test_signal_discovery_classifies_media_player_as_learning_source() -> None:
    suggestions = SignalDiscoveryAudit().run(
        [
            _entity(
                "media_player.projector",
                domain="media_player",
                device_class=None,
                area_name="Living Room",
            )
        ],
        [{"room_id": "living_room"}],
    )

    assert len(suggestions) == 1
    suggestion = suggestions[0]
    assert suggestion.role == "learning_source"
    assert suggestion.signal_name is None
    assert suggestion.confidence == 0.80
    assert suggestion.options_patch.payload == {"entity_id": "media_player.projector"}
    assert "domain=media_player" in suggestion.evidence


def test_signal_discovery_uses_longest_room_match_and_skips_ties() -> None:
    matched = SignalDiscoveryAudit().run(
        [_entity("sensor.studio_lux", area_name="Studio")],
        [{"room_id": "studio"}, {"room_id": "studio_corner"}],
    )
    tied = SignalDiscoveryAudit().run(
        [_entity("sensor.lux", area_name="Studio")],
        [{"room_id": "north_studio"}, {"room_id": "south_studio"}],
    )

    assert matched[0].room_id == "studio_corner"
    assert tied == []


def test_signal_discovery_skips_unmapped_unsupported_and_existing_config() -> None:
    suggestions = SignalDiscoveryAudit().run(
        [
            _entity("sensor.unmapped_lux", area_name=None),
            _entity("sensor.temperature", device_class="temperature"),
            _entity("sensor.studio_lux", device_class="illuminance"),
            _entity("media_player.projector", domain="media_player", device_class=None),
        ],
        [
            {
                "room_id": "studio",
                "signals": [{"signal_name": "room_lux", "entity_id": "sensor.old_lux"}],
                "learning_sources": ["media_player.projector"],
            }
        ],
    )

    assert suggestions == []


def test_signal_discovery_limits_to_first_50_matches_by_entity_id() -> None:
    descriptors = [
        _entity(f"sensor.room_lux_{index:02d}", area_name=f"Room {index:02d}")
        for index in range(60)
    ]
    rooms = [{"room_id": f"room_{index:02d}"} for index in range(60)]

    suggestions = SignalDiscoveryAudit().run(descriptors, rooms)

    assert len(suggestions) == 50
    assert suggestions[0].entity_id == "sensor.room_lux_00"
    assert suggestions[-1].entity_id == "sensor.room_lux_49"


def test_apply_signal_options_patch_adds_room_signal_idempotently() -> None:
    options = {"rooms": [{"room_id": "studio", "signals": []}]}
    patch = SignalOptionsPatch(
        room_id="studio",
        role="room_signal",
        payload={
            "signal_name": "room_lux",
            "entity_id": "sensor.studio_lux",
            "device_class": "illuminance",
            "buckets": [{"label": "dark", "upper_bound": 30}],
        },
    )

    patched, changed = apply_signal_options_patch(options, patch)
    repatched, rechanged = apply_signal_options_patch(patched, patch)

    assert changed is True
    assert patched["rooms"][0]["signals"] == [patch.payload]
    assert options["rooms"][0]["signals"] == []
    assert rechanged is False
    assert repatched == patched


def test_apply_signal_options_patch_adds_learning_source_idempotently() -> None:
    options = {"rooms": [{"room_id": "studio", "learning_sources": []}]}
    patch = SignalOptionsPatch(
        room_id="studio",
        role="learning_source",
        payload={"entity_id": "media_player.projector"},
    )

    patched, changed = apply_signal_options_patch(options, patch)
    repatched, rechanged = apply_signal_options_patch(patched, patch)

    assert changed is True
    assert patched["rooms"][0]["learning_sources"] == ["media_player.projector"]
    assert rechanged is False
    assert repatched == patched


def test_apply_signal_options_patch_skips_missing_room_or_invalid_payload() -> None:
    options = {"rooms": [{"room_id": "studio", "signals": []}]}
    missing_room = SignalOptionsPatch(
        room_id="kitchen",
        role="room_signal",
        payload={"signal_name": "room_lux", "entity_id": "sensor.kitchen_lux"},
    )
    invalid_payload = SignalOptionsPatch(
        room_id="studio",
        role="room_signal",
        payload={"entity_id": "sensor.studio_lux"},
    )

    assert apply_signal_options_patch(options, missing_room) == (options, False)
    assert apply_signal_options_patch(options, invalid_payload) == (options, False)


def test_signal_options_patch_from_dict_validates_shape() -> None:
    patch = SignalOptionsPatch.from_dict(
        {
            "room_id": "studio",
            "role": "learning_source",
            "payload": {"entity_id": "media_player.projector"},
        }
    )

    assert patch == SignalOptionsPatch(
        room_id="studio",
        role="learning_source",
        payload={"entity_id": "media_player.projector"},
    )
    assert SignalOptionsPatch.from_dict({"room_id": "studio", "role": "bad"}) is None


class _ServicesStub:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict, bool]] = []

    async def async_call(
        self,
        domain: str,
        service: str,
        data: dict,
        *,
        blocking: bool,
    ) -> None:
        self.calls.append((domain, service, data, blocking))


@pytest.mark.asyncio
async def test_coordinator_submits_signal_discovery_suggestions_and_notifies() -> None:
    suggestion = SignalDiscoveryAudit().run(
        [_entity("sensor.studio_lux", unit="lx")],
        [{"room_id": "studio"}],
    )[0]
    coordinator = HeimaCoordinator.__new__(HeimaCoordinator)
    coordinator._pending_signal_suggestions = [suggestion]
    coordinator._proposal_engine = SimpleNamespace(
        proposal_by_identity_key=MagicMock(return_value=None),
        async_submit_proposal=AsyncMock(return_value="proposal-signal-1"),
    )
    services = _ServicesStub()
    coordinator.hass = SimpleNamespace(services=services)
    coordinator._notified_installer_alert_keys = set()

    await coordinator._async_evaluate_signal_discovery()

    coordinator._proposal_engine.proposal_by_identity_key.assert_called_once_with(
        "signal_discovery:sensor.studio_lux"
    )
    coordinator._proposal_engine.async_submit_proposal.assert_awaited_once()
    proposal = coordinator._proposal_engine.async_submit_proposal.await_args.args[0]
    assert proposal.analyzer_id == "signal_discovery"
    assert proposal.reaction_type == "signal_discovery"
    assert proposal.origin == "admin_authored"
    assert proposal.followup_kind == "config_suggestion"
    assert proposal.identity_key == "signal_discovery:sensor.studio_lux"
    assert proposal.suggested_reaction_config == suggestion.options_patch.as_dict()
    assert proposal.description == (
        "Entity sensor.studio_lux can be added as room_lux for room 'studio'."
    )
    assert services.calls == [
        (
            "persistent_notification",
            "create",
            {
                "notification_id": "heima_installer_signal_discovery_sensor_studio_lux",
                "title": "Heima: new signal candidate",
                "message": (
                    "Entity sensor.studio_lux detected as room_lux for room 'studio'. "
                    "Confidence: 95%.\n\nProposal ID: proposal-signal-1"
                ),
            },
            False,
        )
    ]
    assert coordinator._notified_installer_alert_keys == {
        "signal_discovery:sensor.studio_lux"
    }


@pytest.mark.asyncio
async def test_coordinator_skips_existing_signal_discovery_proposals() -> None:
    suggestion = SignalDiscoveryAudit().run(
        [_entity("media_player.projector", domain="media_player", device_class=None)],
        [{"room_id": "studio"}],
    )[0]
    coordinator = HeimaCoordinator.__new__(HeimaCoordinator)
    coordinator._pending_signal_suggestions = [suggestion]
    coordinator._proposal_engine = SimpleNamespace(
        proposal_by_identity_key=MagicMock(return_value=object()),
        async_submit_proposal=AsyncMock(return_value="proposal-signal-1"),
    )
    services = _ServicesStub()
    coordinator.hass = SimpleNamespace(services=services)
    coordinator._notified_installer_alert_keys = set()

    await coordinator._async_evaluate_signal_discovery()

    coordinator._proposal_engine.async_submit_proposal.assert_not_awaited()
    assert services.calls == []


def test_reaction_proposal_preserves_config_suggestion_followup_kind() -> None:
    proposal = ReactionProposal.from_dict(
        {
            "analyzer_id": "signal_discovery",
            "reaction_type": "signal_discovery",
            "description": "Signal candidate",
            "confidence": 0.9,
            "origin": "admin_authored",
            "followup_kind": "config_suggestion",
            "suggested_reaction_config": {"room_id": "studio"},
        }
    )

    assert proposal.followup_kind == "config_suggestion"


@pytest.mark.asyncio
async def test_coordinator_reviews_signal_discovery_approval_without_approval_store() -> None:
    proposal = ReactionProposal(
        proposal_id="proposal-signal",
        analyzer_id=SIGNAL_DISCOVERY_ANALYZER_ID,
        reaction_type=SIGNAL_DISCOVERY_REACTION_TYPE,
        identity_key="signal_discovery:sensor.studio_lux",
        suggested_reaction_config={"room_id": "studio"},
    )
    coordinator = HeimaCoordinator.__new__(HeimaCoordinator)
    coordinator._proposal_engine = SimpleNamespace(
        proposal_by_id=MagicMock(return_value=proposal),
        async_accept_proposal=AsyncMock(return_value=True),
        async_reject_proposal=AsyncMock(return_value=False),
    )
    coordinator._notified_installer_alert_keys = {proposal.identity_key}

    result = await coordinator.async_review_proposal(
        "proposal-signal",
        decision="approved",
        approved_by="installer",
    )

    assert result is True
    coordinator._proposal_engine.async_accept_proposal.assert_awaited_once_with(
        "proposal-signal"
    )
    assert proposal.identity_key not in coordinator._notified_installer_alert_keys


@pytest.mark.asyncio
async def test_coordinator_reviews_signal_discovery_rejection() -> None:
    proposal = ReactionProposal(
        proposal_id="proposal-signal",
        analyzer_id=SIGNAL_DISCOVERY_ANALYZER_ID,
        reaction_type=SIGNAL_DISCOVERY_REACTION_TYPE,
        identity_key="signal_discovery:sensor.studio_lux",
        suggested_reaction_config={"room_id": "studio"},
    )
    coordinator = HeimaCoordinator.__new__(HeimaCoordinator)
    coordinator._proposal_engine = SimpleNamespace(
        proposal_by_id=MagicMock(return_value=proposal),
        async_accept_proposal=AsyncMock(return_value=False),
        async_reject_proposal=AsyncMock(return_value=True),
    )
    coordinator._notified_installer_alert_keys = set()

    result = await coordinator.async_review_signal_discovery_proposal(
        "proposal-signal",
        decision="rejected",
    )

    assert result is True
    coordinator._proposal_engine.async_reject_proposal.assert_awaited_once_with(
        "proposal-signal"
    )


@pytest.mark.asyncio
async def test_coordinator_rejects_non_signal_discovery_review() -> None:
    proposal = ReactionProposal(
        proposal_id="proposal-other",
        analyzer_id="semantic_policy_suggestions",
        reaction_type="signal_discovery",
    )
    coordinator = HeimaCoordinator.__new__(HeimaCoordinator)
    coordinator._proposal_engine = SimpleNamespace(
        proposal_by_id=MagicMock(return_value=proposal),
        async_accept_proposal=AsyncMock(return_value=True),
        async_reject_proposal=AsyncMock(return_value=True),
    )

    result = await coordinator.async_review_signal_discovery_proposal(
        "proposal-other",
        decision="approved",
    )

    assert result is False
    coordinator._proposal_engine.async_accept_proposal.assert_not_awaited()


@pytest.mark.asyncio
async def test_coordinator_applies_one_accepted_room_signal_patch() -> None:
    proposal = ReactionProposal(
        proposal_id="proposal-signal",
        analyzer_id=SIGNAL_DISCOVERY_ANALYZER_ID,
        reaction_type=SIGNAL_DISCOVERY_REACTION_TYPE,
        status="accepted",
        suggested_reaction_config={
            "room_id": "studio",
            "role": "room_signal",
            "payload": {
                "signal_name": "room_lux",
                "entity_id": "sensor.studio_lux",
                "device_class": "illuminance",
                "buckets": [{"label": "dark", "upper_bound": 30}],
            },
        },
    )
    entry = SimpleNamespace(options={"rooms": [{"room_id": "studio", "signals": []}]})
    config_entries = SimpleNamespace(async_update_entry=MagicMock())
    coordinator = HeimaCoordinator.__new__(HeimaCoordinator)
    coordinator.entry = entry
    coordinator.hass = SimpleNamespace(config_entries=config_entries)
    coordinator._proposal_engine = SimpleNamespace(accepted_proposals=lambda: [proposal])

    await coordinator._async_apply_accepted_signal_patches()

    config_entries.async_update_entry.assert_called_once()
    assert config_entries.async_update_entry.call_args.kwargs["options"] == {
        "rooms": [
            {
                "room_id": "studio",
                "signals": [
                    {
                        "signal_name": "room_lux",
                        "entity_id": "sensor.studio_lux",
                        "device_class": "illuminance",
                        "buckets": [{"label": "dark", "upper_bound": 30}],
                    }
                ],
            }
        ]
    }


@pytest.mark.asyncio
async def test_coordinator_applies_one_patch_per_cycle() -> None:
    first = ReactionProposal(
        proposal_id="proposal-lux",
        analyzer_id=SIGNAL_DISCOVERY_ANALYZER_ID,
        reaction_type=SIGNAL_DISCOVERY_REACTION_TYPE,
        status="accepted",
        suggested_reaction_config={
            "room_id": "studio",
            "role": "room_signal",
            "payload": {"signal_name": "room_lux", "entity_id": "sensor.studio_lux"},
        },
    )
    second = ReactionProposal(
        proposal_id="proposal-projector",
        analyzer_id=SIGNAL_DISCOVERY_ANALYZER_ID,
        reaction_type=SIGNAL_DISCOVERY_REACTION_TYPE,
        status="accepted",
        suggested_reaction_config={
            "room_id": "studio",
            "role": "learning_source",
            "payload": {"entity_id": "media_player.projector"},
        },
    )
    entry = SimpleNamespace(
        options={"rooms": [{"room_id": "studio", "signals": [], "learning_sources": []}]}
    )
    config_entries = SimpleNamespace(async_update_entry=MagicMock())
    coordinator = HeimaCoordinator.__new__(HeimaCoordinator)
    coordinator.entry = entry
    coordinator.hass = SimpleNamespace(config_entries=config_entries)
    coordinator._proposal_engine = SimpleNamespace(accepted_proposals=lambda: [first, second])

    await coordinator._async_apply_accepted_signal_patches()

    updated_options = config_entries.async_update_entry.call_args.kwargs["options"]
    assert config_entries.async_update_entry.call_count == 1
    assert updated_options["rooms"][0]["signals"] == [
        {"signal_name": "room_lux", "entity_id": "sensor.studio_lux"}
    ]
    assert updated_options["rooms"][0]["learning_sources"] == []


@pytest.mark.asyncio
async def test_coordinator_skips_already_applied_accepted_patch() -> None:
    proposal = ReactionProposal(
        proposal_id="proposal-signal",
        analyzer_id=SIGNAL_DISCOVERY_ANALYZER_ID,
        reaction_type=SIGNAL_DISCOVERY_REACTION_TYPE,
        status="accepted",
        suggested_reaction_config={
            "room_id": "studio",
            "role": "learning_source",
            "payload": {"entity_id": "media_player.projector"},
        },
    )
    entry = SimpleNamespace(
        options={
            "rooms": [
                {"room_id": "studio", "learning_sources": ["media_player.projector"]}
            ]
        }
    )
    config_entries = SimpleNamespace(async_update_entry=MagicMock())
    coordinator = HeimaCoordinator.__new__(HeimaCoordinator)
    coordinator.entry = entry
    coordinator.hass = SimpleNamespace(config_entries=config_entries)
    coordinator._proposal_engine = SimpleNamespace(accepted_proposals=lambda: [proposal])

    await coordinator._async_apply_accepted_signal_patches()

    config_entries.async_update_entry.assert_not_called()


def test_coordinator_builds_signal_discovery_descriptors(monkeypatch: pytest.MonkeyPatch) -> None:
    entity_registry = SimpleNamespace(
        entities={
            "sensor.studio_lux": SimpleNamespace(
                entity_id="sensor.studio_lux",
                device_id="device-lux",
            ),
            "media_player.projector": SimpleNamespace(
                entity_id="media_player.projector",
                area_id="studio_area",
            ),
        }
    )
    device_registry = SimpleNamespace(devices={"device-lux": SimpleNamespace(area_id="studio_area")})
    area_registry = SimpleNamespace(
        async_list_areas=lambda: [SimpleNamespace(id="studio_area", name="Studio")]
    )
    monkeypatch.setattr(
        "custom_components.heima.coordinator.er.async_get",
        lambda _hass: entity_registry,
    )
    monkeypatch.setattr(
        "custom_components.heima.coordinator.dr.async_get",
        lambda _hass: device_registry,
    )
    monkeypatch.setattr(
        "custom_components.heima.coordinator.ar.async_get",
        lambda _hass: area_registry,
    )
    states = [
        SimpleNamespace(
            entity_id="sensor.studio_lux",
            state="42",
            attributes={"device_class": "illuminance", "unit_of_measurement": "lx"},
        ),
        SimpleNamespace(entity_id="media_player.projector", state="playing", attributes={}),
    ]
    coordinator = HeimaCoordinator.__new__(HeimaCoordinator)
    coordinator.hass = SimpleNamespace()
    coordinator._safe_all_states = lambda: states

    descriptors = coordinator._signal_discovery_entity_descriptors()

    by_entity = {descriptor.entity_id: descriptor for descriptor in descriptors}
    assert by_entity["sensor.studio_lux"] == HAEntityDescriptor(
        entity_id="sensor.studio_lux",
        domain="sensor",
        device_class="illuminance",
        unit_of_measurement="lx",
        area_id="studio_area",
        area_name="Studio",
        current_state="42",
    )
    assert by_entity["media_player.projector"].domain == "media_player"
    assert by_entity["media_player.projector"].area_name == "Studio"


@pytest.mark.asyncio
async def test_coordinator_run_signal_discovery_audit_submits_suggestions() -> None:
    suggestions = SignalDiscoveryAudit().run(
        [_entity("sensor.studio_lux", unit="lx")],
        [{"room_id": "studio"}],
    )
    coordinator = HeimaCoordinator.__new__(HeimaCoordinator)
    coordinator.entry = SimpleNamespace(options={"rooms": [{"room_id": "studio"}]})
    coordinator._signal_discovery_audit = SimpleNamespace(run=MagicMock(return_value=suggestions))
    coordinator._signal_discovery_entity_descriptors = MagicMock(return_value=["descriptor"])
    coordinator._proposal_engine = SimpleNamespace(
        proposal_by_identity_key=MagicMock(return_value=None),
        async_submit_proposal=AsyncMock(return_value="proposal-signal"),
    )
    services = _ServicesStub()
    coordinator.hass = SimpleNamespace(services=services)
    coordinator._notified_installer_alert_keys = set()

    result = await coordinator.async_run_signal_discovery()

    assert result == suggestions
    coordinator._signal_discovery_audit.run.assert_called_once_with(
        ["descriptor"],
        [{"room_id": "studio"}],
    )
    coordinator._proposal_engine.async_submit_proposal.assert_awaited_once()


def test_coordinator_schedules_signal_discovery_on_registry_update() -> None:
    listeners: dict[str, object] = {}
    scheduled: list[tuple[int, object]] = []

    class _Bus:
        def async_listen(self, event_type: str, callback):
            listeners[event_type] = callback

            def _unsub() -> None:
                listeners.pop(event_type, None)

            return _unsub

    coordinator = HeimaCoordinator.__new__(HeimaCoordinator)
    coordinator.hass = SimpleNamespace(bus=_Bus(), async_create_task=lambda coro: None)
    coordinator._unsub_signal_discovery_registry = None
    coordinator._unsub_signal_discovery_audit = None

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(
            "custom_components.heima.coordinator.async_call_later",
            lambda _hass, delay, callback: scheduled.append((delay, callback)) or (lambda: None),
        )
        coordinator._subscribe_signal_discovery_registry_updates()
        listeners["entity_registry_updated"](SimpleNamespace())

    assert "entity_registry_updated" in listeners
    assert scheduled and scheduled[0][0] == 0
