"""Built-in primitive activity detectors."""

from .config import build_activity_detectors, normalize_activity_bindings
from .dishwasher import DishwasherDetector
from .oven import OvenOnDetector
from .pc import PcActiveDetector
from .shower import ShowerRunningDetector
from .stove import StoveOnDetector
from .tv import TvActiveDetector
from .washing import WashingMachineDetector

__all__ = [
    "DishwasherDetector",
    "OvenOnDetector",
    "PcActiveDetector",
    "ShowerRunningDetector",
    "StoveOnDetector",
    "TvActiveDetector",
    "WashingMachineDetector",
    "build_activity_detectors",
    "normalize_activity_bindings",
]
