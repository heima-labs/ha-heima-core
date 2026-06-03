"""Rule-based signal discovery for installer-reviewed learning inputs."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from typing import Any, Literal
from uuid import uuid4

SignalRole = Literal["room_signal", "learning_source"]

_MAX_SUGGESTIONS = 50

_SIGNAL_RULES: dict[tuple[str, str], tuple[str, float, list[dict[str, Any]]]] = {
    (
        "sensor",
        "illuminance",
    ): (
        "room_lux",
        0.95,
        [
            {"label": "dark", "upper_bound": 30},
            {"label": "dim", "upper_bound": 100},
            {"label": "ok", "upper_bound": 300},
            {"label": "bright", "upper_bound": None},
        ],
    ),
    (
        "sensor",
        "carbon_dioxide",
    ): (
        "room_co2",
        0.95,
        [
            {"label": "ok", "upper_bound": 800},
            {"label": "elevated", "upper_bound": 1200},
            {"label": "high", "upper_bound": None},
        ],
    ),
    (
        "sensor",
        "humidity",
    ): (
        "room_humidity",
        0.90,
        [
            {"label": "low", "upper_bound": 40},
            {"label": "ok", "upper_bound": 70},
            {"label": "high", "upper_bound": None},
        ],
    ),
}


@dataclass(frozen=True)
class HAEntityDescriptor:
    """Read-only descriptor built from HA entity registry and current state."""

    entity_id: str
    domain: str
    device_class: str | None
    unit_of_measurement: str | None
    area_id: str | None
    area_name: str | None
    current_state: str | None


@dataclass(frozen=True)
class SignalOptionsPatch:
    """Typed description of what to add to options on approval."""

    room_id: str
    role: SignalRole
    payload: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "SignalOptionsPatch | None":
        if not isinstance(raw, dict):
            return None
        room_id = _clean(raw.get("room_id"))
        role = _clean(raw.get("role"))
        payload = raw.get("payload")
        if not room_id or role not in {"room_signal", "learning_source"}:
            return None
        if not isinstance(payload, dict):
            return None
        return cls(
            room_id=room_id,
            role=role,  # type: ignore[arg-type]
            payload=dict(payload),
        )


@dataclass(frozen=True)
class SignalSuggestion:
    """Installer-reviewable signal discovery result for one HA entity."""

    suggestion_id: str
    entity_id: str
    room_id: str
    role: SignalRole
    signal_name: str | None
    device_class: str | None
    confidence: float
    evidence: list[str]
    options_patch: SignalOptionsPatch
    identity_key: str

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["options_patch"] = self.options_patch.as_dict()
        return data


class SignalDiscoveryAudit:
    """Classify HA entities into signal suggestions without touching runtime state."""

    def run(
        self,
        entity_descriptors: list[HAEntityDescriptor],
        heima_rooms: list[dict[str, Any]],
    ) -> list[SignalSuggestion]:
        suggestions: list[SignalSuggestion] = []
        seen_entity_ids: set[str] = set()
        for descriptor in sorted(entity_descriptors, key=lambda item: item.entity_id):
            entity_id = _clean(descriptor.entity_id)
            if not entity_id or entity_id in seen_entity_ids:
                continue
            seen_entity_ids.add(entity_id)
            suggestion = self._suggestion_for_descriptor(descriptor, heima_rooms)
            if suggestion is not None:
                suggestions.append(suggestion)
            if len(suggestions) >= _MAX_SUGGESTIONS:
                break
        return suggestions

    def _suggestion_for_descriptor(
        self,
        descriptor: HAEntityDescriptor,
        heima_rooms: list[dict[str, Any]],
    ) -> SignalSuggestion | None:
        entity_id = _clean(descriptor.entity_id)
        domain = _clean_lower(descriptor.domain)
        device_class = _clean_lower(descriptor.device_class)
        room_id = _match_room_id(descriptor.area_name, heima_rooms)
        if room_id is None:
            return None

        if domain == "media_player":
            if _learning_source_exists(heima_rooms, room_id, entity_id):
                return None
            return _learning_source_suggestion(descriptor, room_id)

        rule = _SIGNAL_RULES.get((domain, device_class))
        if rule is None:
            return None

        signal_name, confidence, buckets = rule
        if _room_signal_exists(heima_rooms, room_id, signal_name):
            return None
        return _room_signal_suggestion(
            descriptor,
            room_id=room_id,
            signal_name=signal_name,
            confidence=confidence,
            buckets=buckets,
        )


def apply_signal_options_patch(
    options: dict[str, Any],
    patch: SignalOptionsPatch,
) -> tuple[dict[str, Any], bool]:
    """Return options with one additive signal discovery patch applied if needed."""
    patched = deepcopy(dict(options))
    rooms = patched.get("rooms", [])
    if not isinstance(rooms, list):
        return patched, False

    room = _room_by_id(rooms, patch.room_id)
    if room is None:
        return patched, False

    if patch.role == "room_signal":
        return _apply_room_signal_patch(patched, room, patch)
    if patch.role == "learning_source":
        return _apply_learning_source_patch(patched, room, patch)
    return patched, False


def _apply_room_signal_patch(
    options: dict[str, Any],
    room: dict[str, Any],
    patch: SignalOptionsPatch,
) -> tuple[dict[str, Any], bool]:
    signal_name = _clean(patch.payload.get("signal_name"))
    entity_id = _clean(patch.payload.get("entity_id"))
    if not signal_name or not entity_id:
        return options, False
    signals = room.get("signals", [])
    if not isinstance(signals, list):
        signals = []
    if any(
        isinstance(signal, dict) and _clean(signal.get("signal_name")) == signal_name
        for signal in signals
    ):
        return options, False
    room["signals"] = [*signals, dict(patch.payload)]
    return options, True


def _apply_learning_source_patch(
    options: dict[str, Any],
    room: dict[str, Any],
    patch: SignalOptionsPatch,
) -> tuple[dict[str, Any], bool]:
    entity_id = _clean(patch.payload.get("entity_id"))
    if not entity_id:
        return options, False
    sources = room.get("learning_sources", [])
    if not isinstance(sources, list):
        sources = []
    if entity_id in {_clean(source) for source in sources}:
        return options, False
    room["learning_sources"] = [*sources, entity_id]
    return options, True


def _room_signal_suggestion(
    descriptor: HAEntityDescriptor,
    *,
    room_id: str,
    signal_name: str,
    confidence: float,
    buckets: list[dict[str, Any]],
) -> SignalSuggestion:
    device_class = _clean_lower(descriptor.device_class)
    payload = {
        "signal_name": signal_name,
        "entity_id": _clean(descriptor.entity_id),
        "device_class": device_class,
        "buckets": [dict(bucket) for bucket in buckets],
    }
    return SignalSuggestion(
        suggestion_id=str(uuid4()),
        entity_id=_clean(descriptor.entity_id),
        room_id=room_id,
        role="room_signal",
        signal_name=signal_name,
        device_class=device_class,
        confidence=confidence,
        evidence=_evidence(
            descriptor,
            room_id=room_id,
            domain=False,
            device_class=True,
        ),
        options_patch=SignalOptionsPatch(
            room_id=room_id,
            role="room_signal",
            payload=payload,
        ),
        identity_key=f"signal_discovery:{_clean(descriptor.entity_id)}",
    )


def _learning_source_suggestion(
    descriptor: HAEntityDescriptor,
    room_id: str,
) -> SignalSuggestion:
    entity_id = _clean(descriptor.entity_id)
    return SignalSuggestion(
        suggestion_id=str(uuid4()),
        entity_id=entity_id,
        room_id=room_id,
        role="learning_source",
        signal_name=None,
        device_class=_clean_lower(descriptor.device_class) or None,
        confidence=0.80,
        evidence=_evidence(
            descriptor,
            room_id=room_id,
            domain=True,
            device_class=False,
        ),
        options_patch=SignalOptionsPatch(
            room_id=room_id,
            role="learning_source",
            payload={"entity_id": entity_id},
        ),
        identity_key=f"signal_discovery:{entity_id}",
    )


def _evidence(
    descriptor: HAEntityDescriptor,
    *,
    room_id: str,
    domain: bool,
    device_class: bool,
) -> list[str]:
    evidence: list[str] = []
    if domain:
        evidence.append(f"domain={_clean_lower(descriptor.domain)}")
    if device_class and _clean_lower(descriptor.device_class):
        evidence.append(f"device_class={_clean_lower(descriptor.device_class)}")
    if _clean(descriptor.unit_of_measurement):
        evidence.append(f"unit={_clean(descriptor.unit_of_measurement)}")
    if _clean(descriptor.area_name):
        evidence.append(f"area={_clean(descriptor.area_name)}")
    evidence.append(f"matched room: {room_id} (area: {_clean(descriptor.area_name)})")
    return evidence


def _match_room_id(area_name: str | None, heima_rooms: list[dict[str, Any]]) -> str | None:
    normalized_area = _normalize_room_name(area_name)
    if not normalized_area:
        return None

    matches: list[tuple[str, str]] = []
    for room in heima_rooms:
        room_id = _clean(room.get("room_id"))
        normalized_room_id = _normalize_room_name(room_id)
        if not room_id or not normalized_room_id:
            continue
        if normalized_area == normalized_room_id:
            matches.append((room_id, normalized_room_id))
            continue
        if normalized_area in normalized_room_id or normalized_room_id in normalized_area:
            matches.append((room_id, normalized_room_id))

    if not matches:
        return None
    if len(matches) == 1:
        return matches[0][0]

    max_len = max(len(normalized_room_id) for _, normalized_room_id in matches)
    longest = [match for match in matches if len(match[1]) == max_len]
    if len(longest) == 1:
        return longest[0][0]
    return None


def _room_signal_exists(
    heima_rooms: list[dict[str, Any]],
    room_id: str,
    signal_name: str,
) -> bool:
    room = _room_by_id(heima_rooms, room_id)
    if room is None:
        return False
    signals = room.get("signals", [])
    if not isinstance(signals, list):
        return False
    return any(
        isinstance(signal, dict) and _clean(signal.get("signal_name")) == signal_name
        for signal in signals
    )


def _learning_source_exists(
    heima_rooms: list[dict[str, Any]],
    room_id: str,
    entity_id: str,
) -> bool:
    room = _room_by_id(heima_rooms, room_id)
    if room is None:
        return False
    sources = room.get("learning_sources", [])
    if not isinstance(sources, list):
        return False
    return entity_id in {_clean(source) for source in sources}


def _room_by_id(heima_rooms: list[dict[str, Any]], room_id: str) -> dict[str, Any] | None:
    for room in heima_rooms:
        if _clean(room.get("room_id")) == room_id:
            return room
    return None


def _normalize_room_name(value: str | None) -> str:
    return _clean_lower(value).replace("_", " ")


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _clean_lower(value: Any) -> str:
    return _clean(value).lower()
