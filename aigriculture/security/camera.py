"""Security camera — low-lag intruder detection.

Keeping a CPU-only Pi smooth comes down to three cheap tricks, all here:

  1. FRAME-SKIP   — run the detector on every Nth frame, not every frame.
                    The stream still shows every frame; only inference is throttled.
  2. CLASS FILTER — the detector is built with an allow-list (person, animals),
                    so it ignores the ~70 other COCO classes it doesn't care about.
  3. SMALL INPUT  — a small imgsz (set when the detector is built) keeps each
                    inference fast.

A confirmed threat fires an `on_threat` callback (wired by the app to the siren,
a stored snapshot, and a dashboard alert), rate-limited by a cooldown.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, List, Optional

import numpy as np

from ..camera.base import CameraSource
from ..inference.base import Detection, Detector

try:
    import cv2
except ImportError:  # pragma: no cover
    cv2 = None  # type: ignore

# COCO classes worth alarming on. Edit to taste.
DEFAULT_THREAT_CLASSES = ["person", "cat", "dog", "bird", "horse", "sheep", "cow", "bear"]

ThreatCallback = Callable[[List[Detection], np.ndarray], None]


class SecurityCamera:
    def __init__(
        self,
        camera: CameraSource,
        detector: Detector,
        detect_every: int = 3,
        cooldown_s: float = 15.0,
        on_threat: Optional[ThreatCallback] = None,
        draw: bool = True,
    ):
        self.camera = camera
        self.detector = detector
        self.detect_every = max(1, detect_every)
        self.cooldown_s = cooldown_s
        self.on_threat = on_threat
        self.draw = draw

        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._latest: Optional[np.ndarray] = None
        self._last_dets: List[Detection] = []
        self._last_alert = 0.0
        self.frames_seen = 0

    # ── lifecycle ────────────────────────────────────────────────────────────
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="security-cam", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)
        self.camera.release()

    # ── main loop ────────────────────────────────────────────────────────────
    def _loop(self) -> None:
        det_fail_count = 0
        while not self._stop.is_set():
            try:
                ok, frame = self.camera.read()
            except Exception:
                time.sleep(0.2)
                continue
            if not ok or frame is None:
                time.sleep(0.05)
                continue
            self.frames_seen += 1

            dets = self._last_dets
            if self.frames_seen % self.detect_every == 0:
                try:
                    dets = self.detector.detect(frame)
                    self._last_dets = dets
                    det_fail_count = 0
                    if dets:
                        self._maybe_alert(dets, frame)
                except Exception as e:
                    det_fail_count += 1
                    if det_fail_count <= 3:
                        print(f"[WARN] security detector raised: {e}")
                    # Keep streaming the raw frame so the dashboard still shows video.
                    time.sleep(0.1)

            annotated = self._annotate(frame, dets) if self.draw else frame
            with self._lock:
                self._latest = annotated

    def _maybe_alert(self, dets: List[Detection], frame: np.ndarray) -> None:
        now = time.monotonic()
        if now - self._last_alert < self.cooldown_s:
            return
        self._last_alert = now
        if self.on_threat:
            try:
                self.on_threat(dets, frame.copy())
            except Exception:
                pass  # an alert sink must never crash the camera loop

    # ── helpers ────────────────────────────────────────────────────────────
    def _annotate(self, frame: np.ndarray, dets: List[Detection]) -> np.ndarray:
        if cv2 is None or not dets:
            return frame
        img = frame.copy()
        for d in dets:
            x1, y1, x2, y2 = d.bbox
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 255), 2)
            cv2.putText(img, f"{d.label} {d.confidence:.2f}", (x1, max(0, y1 - 6)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1, cv2.LINE_AA)
        return img

    def latest_frame(self) -> Optional[np.ndarray]:
        with self._lock:
            return None if self._latest is None else self._latest.copy()

    def latest_jpeg(self, quality: int = 70) -> Optional[bytes]:
        frame = self.latest_frame()
        if frame is None or cv2 is None:
            return None
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
        return buf.tobytes() if ok else None

    @property
    def status(self) -> dict:
        return {
            "frames_seen": self.frames_seen,
            "detections": [
                {"label": d.label, "confidence": round(d.confidence, 3), "bbox": list(d.bbox)}
                for d in self._last_dets
            ],
            "running": bool(self._thread and self._thread.is_alive()),
        }
