"""Object-detection abstraction.

One detector interface, two backends:

    cpu    -> Ultralytics YOLO on the CPU (DEFAULT, runs on any Pi)
    hailo  -> Hailo-10H .hef on the AI HAT (OPTIONAL, much faster)

Callers depend only on `Detector` and `Detection` and never import a backend
directly — `build_detector()` picks the implementation.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple

import numpy as np


@dataclass
class Detection:
    label: str
    confidence: float
    bbox: Tuple[int, int, int, int]  # x1, y1, x2, y2 in pixels


class Detector(abc.ABC):
    """Runs detection on a single BGR frame and returns boxes."""

    def __init__(
        self,
        model_path: str,
        conf_threshold: float = 0.45,
        classes: Optional[Iterable[str]] = None,
        imgsz: int = 640,
    ):
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        # Lower-cased allow-list of class names; None means "keep everything".
        self.classes = {c.lower() for c in classes} if classes else None
        self.imgsz = imgsz

    @abc.abstractmethod
    def detect(self, frame: np.ndarray) -> List[Detection]:
        ...

    def _keep(self, label: str, conf: float) -> bool:
        if conf < self.conf_threshold:
            return False
        if self.classes is not None and label.lower() not in self.classes:
            return False
        return True

    def close(self) -> None:  # backends override if they hold resources
        pass


def build_detector(backend: str = "cpu", **kwargs) -> Detector:
    """Construct a detector. backend is 'cpu' (default) or 'hailo'."""
    backend = (backend or "cpu").lower()
    if backend in ("cpu", "yolo", "pytorch", "pt"):
        from .yolo_cpu import YoloCpuDetector
        return YoloCpuDetector(**kwargs)
    if backend in ("hailo", "hef"):
        from .hailo import HailoDetector
        return HailoDetector(**kwargs)
    raise ValueError(f"unknown inference backend {backend!r} (use 'cpu' or 'hailo')")
