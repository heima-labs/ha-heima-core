"""Activity detector binding normalization and factory helpers."""

from __future__ import annotations

from typing import Any

from ...const import DEFAULT_ACTIVITY_BINDINGS
from ..plugin_contracts import IActivityDetector
from .dishwasher import DishwasherDetector
from .oven import OvenOnDetector
from .pc import PcActiveDetector
from .shower import ShowerRunningDetector
from .stove import StoveOnDetector
from .tv import TvActiveDetector
from .washing import WashingMachineDetector

_DETECTOR_CLASSES = {
    "stove_on": StoveOnDetector,
    "oven_on": OvenOnDetector,
    "tv_active": TvActiveDetector,
    "pc_active": PcActiveDetector,
    "shower_running": ShowerRunningDetector,
    "washing_machine_running": WashingMachineDetector,
    "dishwasher_running": DishwasherDetector,
}


def normalize_activity_bindings(raw: Any) -> dict[str, dict[str, Any]]:
    """Normalize activity binding options while preserving explicit empty bindings."""
    source = raw if isinstance(raw, dict) else {}
    normalized: dict[str, dict[str, Any]] = {}
    for activity_name, defaults in DEFAULT_ACTIVITY_BINDINGS.items():
        configured = source.get(activity_name, {})
        cfg = dict(configured) if isinstance(configured, dict) else {}
        entity_key = str(defaults.get("entity_key") or "")
        entity_id = str(cfg.get("entity_id") or cfg.get(entity_key) or "").strip()
        item = {key: value for key, value in defaults.items() if key not in {"entity_key"}}
        item.update({key: value for key, value in cfg.items() if key != entity_key})
        item["entity_id"] = entity_id
        if "room_id" in cfg:
            item["room_id"] = str(cfg.get("room_id") or "").strip() or None
        normalized[activity_name] = item
    return normalized


def build_activity_detectors(bindings: Any) -> list[IActivityDetector]:
    """Build primitive activity detectors from normalized activity bindings."""
    normalized = normalize_activity_bindings(bindings)
    detectors: list[IActivityDetector] = []
    for activity_name, cfg in normalized.items():
        detector_cls = _DETECTOR_CLASSES.get(activity_name)
        if detector_cls is None:
            continue
        entity_id = str(cfg.get("entity_id") or "").strip()
        if not entity_id:
            continue
        kwargs = dict(cfg)
        kwargs["entity_id"] = entity_id
        detectors.append(detector_cls(**kwargs))
    return detectors
