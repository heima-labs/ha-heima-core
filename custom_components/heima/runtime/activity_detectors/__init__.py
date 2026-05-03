"""Built-in primitive activity detectors."""

from .dishwasher import DishwasherDetector
from .oven import OvenOnDetector
from .pc import PcActiveDetector
from .stove import StoveOnDetector
from .tv import TvActiveDetector
from .washing import WashingMachineDetector

__all__ = [
    "DishwasherDetector",
    "OvenOnDetector",
    "PcActiveDetector",
    "StoveOnDetector",
    "TvActiveDetector",
    "WashingMachineDetector",
]
