"""CPU YOLO backend (Ultralytics) — the default detector.

Works on a plain Raspberry Pi with no accelerator. For a smooth security feed,
pair this with frame-skipping and a class allow-list (see aigriculture/security)
and keep imgsz small (320-480).
"""

from __future__ import annotations

from typing import List

import numpy as np

from .base import Detection, Detector

try:
    from ultralytics import YOLO
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "ultralytics is required for the CPU backend: pip install ultralytics"
    ) from e


class YoloCpuDetector(Detector):
    def __init__(self, model_path: str = "yolo11n.pt", **kwargs):
        super().__init__(model_path, **kwargs)
        # Ultralytics downloads stock weights (yolo11n.pt, yolov8n.pt) on first use,
        # or loads a custom .pt by path.
        self.model = YOLO(model_path)
        self._names = self.model.names  # {id: name}

    def detect(self, frame: np.ndarray) -> List[Detection]:
        results = self.model.predict(
            frame,
            conf=self.conf_threshold,
            imgsz=self.imgsz,
            verbose=False,
        )
        out: List[Detection] = []
        for r in results:
            boxes = getattr(r, "boxes", None)
            if boxes is None:
                continue
            for b in boxes:
                cls_id = int(b.cls[0])
                label = self._names.get(cls_id, str(cls_id))
                conf = float(b.conf[0])
                if not self._keep(label, conf):
                    continue
                x1, y1, x2, y2 = (int(v) for v in b.xyxy[0].tolist())
                out.append(Detection(label=label, confidence=conf, bbox=(x1, y1, x2, y2)))
        return out
