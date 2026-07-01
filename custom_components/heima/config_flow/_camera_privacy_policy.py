"""Camera privacy policy materialization helpers."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from homeassistant.util import slugify

from ..const import HOUSE_STATES_CANONICAL, OPT_REACTIONS
from ..runtime.reactions.alarm_policy import normalize_alarm_state_action_config

CAMERA_PRIVACY_POLICY_TYPE = "security.camera_privacy_policy"
CAMERA_PRIVACY_POLICY_METADATA_KEY = "camera_privacy_policy"
CAMERA_PRIVACY_ALARM_STATES = (
    "disarmed",
    "armed_home",
    "armed_away",
    "armed_night",
    "triggered",
)
CAMERA_PRIVACY_HOUSE_FILTERS = ("always", "only", "except")
CAMERA_PRIVACY_ACTIONS = ("turn_on", "turn_off")


@dataclass(frozen=True)
class CameraPrivacyPolicyRow:
    """Bounded UI/domain row for camera privacy policy authoring."""

    camera_source_id: str
    privacy_entity: str
    alarm_states: tuple[str, ...]
    house_filter_mode: str = "always"
    house_states: tuple[str, ...] = ()
    privacy_action: str = "turn_on"
    enabled: bool = True
    camera_display_name: str = ""
    created_at: str = ""


@dataclass(frozen=True)
class CameraPrivacyPolicyMaterialization:
    """Materialized configured-reaction payload plus presentation metadata."""

    reaction_id: str
    config: dict[str, Any]
    label: str


def materialize_camera_privacy_policy_row(
    row: CameraPrivacyPolicyRow,
    *,
    existing_configured: dict[str, Any] | None = None,
) -> CameraPrivacyPolicyMaterialization:
    """Materialize one camera privacy policy row into a configured reaction entry."""
    normalized = _normalized_row(row)
    config = normalize_alarm_state_action_config(
        {
            "reaction_type": "alarm_state_action",
            "enabled": bool(normalized.enabled),
            "origin": "admin_authored",
            "author_kind": "admin",
            "admin_authored_template_id": CAMERA_PRIVACY_POLICY_TYPE,
            "source_template_id": CAMERA_PRIVACY_POLICY_TYPE,
            "source_request": f"template:{CAMERA_PRIVACY_POLICY_TYPE}",
            "created_at": normalized.created_at,
            "alarm_states": list(normalized.alarm_states),
            **_house_state_filter_config(normalized),
            "steps": [
                {
                    "domain": "switch",
                    "target": normalized.privacy_entity,
                    "action": f"switch.{normalized.privacy_action}",
                    "params": {"entity_id": normalized.privacy_entity},
                }
            ],
            CAMERA_PRIVACY_POLICY_METADATA_KEY: {
                "camera_source_id": normalized.camera_source_id,
                "privacy_entity": normalized.privacy_entity,
                "house_filter_mode": normalized.house_filter_mode,
                "house_states": list(normalized.house_states),
                "privacy_action": normalized.privacy_action,
            },
        }
    )
    if not normalized.created_at:
        config.pop("created_at", None)
    label = camera_privacy_policy_label(normalized)
    reaction_id = _reaction_id_for_row(normalized, config, existing_configured or {})
    return CameraPrivacyPolicyMaterialization(reaction_id=reaction_id, config=config, label=label)


def apply_camera_privacy_policy_rows_to_options(
    options: dict[str, Any],
    rows: list[CameraPrivacyPolicyRow],
) -> dict[str, Any]:
    """Replace managed camera privacy policies while preserving unrelated options."""
    updated_options = dict(options or {})
    reactions = dict(updated_options.get(OPT_REACTIONS, {}) or {})
    configured = dict(reactions.get("configured", {}) or {})
    labels = dict(reactions.get("labels", {}) or {})

    for reaction_id, cfg in list(configured.items()):
        if _is_camera_privacy_policy_config(cfg):
            configured.pop(reaction_id, None)
            labels.pop(reaction_id, None)

    for row in rows:
        materialized = materialize_camera_privacy_policy_row(
            row,
            existing_configured=configured,
        )
        configured[materialized.reaction_id] = materialized.config
        labels[materialized.reaction_id] = materialized.label

    reactions["configured"] = configured
    reactions["labels"] = labels
    updated_options[OPT_REACTIONS] = reactions
    return updated_options


def camera_privacy_policy_label(row: CameraPrivacyPolicyRow) -> str:
    """Return the human label persisted in reactions.labels."""
    normalized = _normalized_row(row)
    camera_label = normalized.camera_display_name or normalized.camera_source_id
    action_label = "on" if normalized.privacy_action == "turn_on" else "off"
    states_label = ", ".join(normalized.alarm_states)
    if normalized.house_filter_mode == "only":
        house_label = f" only {'/'.join(normalized.house_states)}"
    elif normalized.house_filter_mode == "except":
        house_label = f" except {'/'.join(normalized.house_states)}"
    else:
        house_label = ""
    return f"{camera_label} privacy: {action_label} when alarm is {states_label}{house_label}"


def _normalized_row(row: CameraPrivacyPolicyRow) -> CameraPrivacyPolicyRow:
    camera_source_id = _require_slug(row.camera_source_id, "camera_source_id")
    privacy_entity = str(row.privacy_entity or "").strip()
    if not privacy_entity.startswith("switch."):
        raise ValueError("privacy_entity must be a switch entity")

    alarm_states = _ordered_known_values(
        row.alarm_states,
        valid_values=CAMERA_PRIVACY_ALARM_STATES,
        field="alarm_states",
    )
    if not alarm_states:
        raise ValueError("alarm_states must not be empty")

    house_filter_mode = str(row.house_filter_mode or "always").strip()
    if house_filter_mode not in CAMERA_PRIVACY_HOUSE_FILTERS:
        raise ValueError("house_filter_mode is invalid")
    house_states = _ordered_known_values(
        row.house_states,
        valid_values=tuple(HOUSE_STATES_CANONICAL),
        field="house_states",
    )
    if house_filter_mode in {"only", "except"} and not house_states:
        raise ValueError("house_states must not be empty for filtered policies")
    if house_filter_mode == "always":
        house_states = ()

    privacy_action = str(row.privacy_action or "").strip()
    if privacy_action not in CAMERA_PRIVACY_ACTIONS:
        raise ValueError("privacy_action is invalid")

    return CameraPrivacyPolicyRow(
        camera_source_id=camera_source_id,
        privacy_entity=privacy_entity,
        alarm_states=alarm_states,
        house_filter_mode=house_filter_mode,
        house_states=house_states,
        privacy_action=privacy_action,
        enabled=bool(row.enabled),
        camera_display_name=str(row.camera_display_name or "").strip(),
        created_at=str(row.created_at or "").strip(),
    )


def _house_state_filter_config(row: CameraPrivacyPolicyRow) -> dict[str, list[str]]:
    if row.house_filter_mode == "only":
        return {"only_house_states": list(row.house_states)}
    if row.house_filter_mode == "except":
        return {"skip_house_states": list(row.house_states)}
    return {}


def _reaction_id_for_row(
    row: CameraPrivacyPolicyRow,
    config: dict[str, Any],
    existing_configured: dict[str, Any],
) -> str:
    base = "__".join(
        (
            "camera_privacy_policy",
            _slug_part(row.camera_source_id),
            _slug_part("-".join(row.alarm_states)),
            _house_filter_slug(row),
            row.privacy_action,
        )
    )
    existing = existing_configured.get(base)
    if not isinstance(existing, dict) or _canonical_payload(existing) == _canonical_payload(config):
        return base

    digest = hashlib.sha1(_canonical_payload(config).encode("utf-8")).hexdigest()
    for length in (8, 12, 16, 20, 40):
        candidate = f"{base}__{digest[:length]}"
        existing = existing_configured.get(candidate)
        if not isinstance(existing, dict) or _canonical_payload(existing) == _canonical_payload(
            config
        ):
            return candidate
    return f"{base}__{digest}"


def _house_filter_slug(row: CameraPrivacyPolicyRow) -> str:
    if row.house_filter_mode == "only":
        return f"only_{_slug_part('-'.join(row.house_states))}"
    if row.house_filter_mode == "except":
        return f"except_{_slug_part('-'.join(row.house_states))}"
    return "any"


def _is_camera_privacy_policy_config(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    if str(value.get("source_template_id") or "").strip() == CAMERA_PRIVACY_POLICY_TYPE:
        return True
    return isinstance(value.get(CAMERA_PRIVACY_POLICY_METADATA_KEY), dict)


def _ordered_known_values(
    values: tuple[str, ...],
    *,
    valid_values: tuple[str, ...],
    field: str,
) -> tuple[str, ...]:
    cleaned = {str(value or "").strip() for value in values if str(value or "").strip()}
    invalid = sorted(cleaned - set(valid_values))
    if invalid:
        raise ValueError(f"{field} contains invalid values")
    return tuple(value for value in valid_values if value in cleaned)


def _require_slug(value: str, field: str) -> str:
    cleaned = str(value or "").strip()
    if not cleaned or _slug_part(cleaned) != cleaned:
        raise ValueError(f"{field} must be a slug")
    return cleaned


def _slug_part(value: str) -> str:
    return str(slugify(str(value or "").strip()).replace("-", "_") or "unknown")


def _canonical_payload(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
