"""Hailo-10H backend (OPTIONAL) — runs a compiled .hef on the AI HAT.

This path only matters if you own a Hailo accelerator and want higher FPS.
If the Hailo SDK is not installed, the system simply uses the CPU backend.

It targets HEFs compiled WITH on-chip NMS (the usual Ultralytics -> Hailo
export), whose output is one detection list per class:
    [y_min, x_min, y_max, x_max, score]  in normalized [0,1] coordinates.
Pass `labels=[...]` ordered to match the model's classes.
"""

from __future__ import annotations

from typing import List, Optional, Sequence

import numpy as np

from .base import Detection, Detector

try:
    from hailo_platform import VDevice, HEF, FormatType  # type: ignore
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False

try:
    import cv2
except ImportError:  # pragma: no cover
    cv2 = None  # type: ignore


class HailoDetector(Detector):
    def __init__(self, model_path: str, labels: Optional[Sequence[str]] = None, **kwargs):
        super().__init__(model_path, **kwargs)
        if not _AVAILABLE:
            raise ImportError(
                "Hailo SDK (hailo_platform) not found. Install HailoRT for the "
                "Hailo backend, or use --backend cpu (the default)."
            )
        self.labels = list(labels) if labels else []
        self._vdevice = VDevice(VDevice.create_params())
        self._model = self._vdevice.create_infer_model(model_path)
        self._model.set_batch_size(1)
        self._configured = self._model.configure()
        _, h, w, _ = self._model.input().shape  # NHWC
        self._in_w, self._in_h = int(w), int(h)

    def _preprocess(self, frame: np.ndarray) -> np.ndarray:
        if cv2 is None:
            raise RuntimeError("opencv-python is required for Hailo preprocessing")
        resized = cv2.resize(frame, (self._in_w, self._in_h))
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        return np.ascontiguousarray(rgb, dtype=np.uint8)

    def detect(self, frame: np.ndarray) -> List[Detection]:
        h0, w0 = frame.shape[:2]
        bindings = self._configured.create_bindings()
        bindings.input().set_buffer(self._preprocess(frame))
        self._configured.run([bindings], timeout=5000)
        raw = bindings.output().get_buffer()

        out: List[Detection] = []
        # NMS output: list indexed by class id; each row is a detection.
        for cls_id, dets in enumerate(raw):
            if dets is None or len(dets) == 0:
                continue
            label = self.labels[cls_id] if cls_id < len(self.labels) else str(cls_id)
            for det in dets:
                y1, x1, y2, x2, score = det[:5]
                if not self._keep(label, float(score)):
                    continue
                out.append(Detection(
                    label=label,
                    confidence=float(score),
                    bbox=(int(x1 * w0), int(y1 * h0), int(x2 * w0), int(y2 * h0)),
                ))
        return out

    def close(self) -> None:
        try:
            self._configured.__exit__(None, None, None)
        except Exception:
            pass
