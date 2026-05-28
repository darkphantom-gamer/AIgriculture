"""FarmMonitor — scheduled disease + ripeness scanning.

Captures a short batch of frames from the FarmMonitor camera, runs the disease
and ripeness YOLO models over them, aggregates the verdict, stores the result,
and (optionally) emails an alert. Disabled gracefully if the .pt models or the
camera are missing.
"""

from __future__ import annotations

import json
import threading
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Optional

from .. import config, notify
from ..inference.base import Detector, build_detector

try:
    import cv2
except ImportError:
    cv2 = None  # type: ignore

BLUR_THRESHOLD = 100.0  # reject frames with Laplacian variance below this


class FarmMonitor:
    def __init__(self, state, camera, disease_model: str, ripeness_model: str,
                 app_config: dict, conf: float = 0.45, batch: int = 8, interval_s: int = 3600):
        self.state = state
        self.camera = camera
        self.app_config = app_config or {}
        self.batch = batch
        self.interval_s = interval_s

        self._status = {"state": "idle", "message": "", "last_result": None}
        self._lock = threading.Lock()
        self._scan_req = threading.Event()
        self._stop = threading.Event()

        self.disease: Optional[Detector] = self._maybe_detector(disease_model, conf)
        self.ripeness: Optional[Detector] = self._maybe_detector(ripeness_model, conf)
        self.enabled = bool(self.camera and (self.disease or self.ripeness))

    @staticmethod
    def _maybe_detector(model_path: str, conf: float) -> Optional[Detector]:
        if not model_path or not Path(model_path).exists():
            return None
        try:
            return build_detector("cpu", model_path=model_path, conf_threshold=conf, imgsz=640)
        except Exception as e:
            print(f"[WARN] FarmMonitor model {model_path} unavailable: {e}")
            return None

    # ── lifecycle ────────────────────────────────────────────────────────────
    def start(self) -> None:
        if not self.enabled:
            self._set(state="disabled", message="no FarmMonitor camera or models")
            return
        threading.Thread(target=self._loop, name="farmmonitor", daemon=True).start()

    def stop(self) -> None:
        self._stop.set()

    def request_scan(self) -> None:
        self._scan_req.set()

    def status(self) -> dict:
        with self._lock:
            return dict(self._status)

    def _set(self, **updates) -> None:
        with self._lock:
            self._status.update(updates)

    # ── scan loop ────────────────────────────────────────────────────────────
    def _loop(self) -> None:
        next_auto = time.time() + self.interval_s
        while not self._stop.is_set():
            triggered = self._scan_req.wait(timeout=2.0)
            if triggered:
                self._scan_req.clear()
            elif time.time() >= next_auto:
                triggered = True
                next_auto = time.time() + self.interval_s
            if triggered:
                try:
                    self._run_scan()
                except Exception as e:
                    self._set(state="error", message=str(e))

    def _is_blurry(self, frame) -> bool:
        if cv2 is None:
            return False
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return cv2.Laplacian(gray, cv2.CV_64F).var() < BLUR_THRESHOLD

    def _run_scan(self) -> None:
        self._set(state="scanning", message="capturing frames")
        disease_tally: Counter = Counter()
        ripeness_tally: Counter = Counter()
        best_conf, best_frame = 0.0, None

        captured = 0
        for _ in range(self.batch * 2):
            if captured >= self.batch:
                break
            ok, frame = self.camera.read()
            if not ok or frame is None or self._is_blurry(frame):
                time.sleep(0.2)
                continue
            captured += 1
            for det in (self.disease.detect(frame) if self.disease else []):
                disease_tally[det.label] += 1
                if det.confidence > best_conf:
                    best_conf, best_frame = det.confidence, frame
            for det in (self.ripeness.detect(frame) if self.ripeness else []):
                ripeness_tally[det.label] += 1
            time.sleep(0.1)

        disease_best = disease_tally.most_common(1)[0][0] if disease_tally else None
        ripeness_best = ripeness_tally.most_common(1)[0][0] if ripeness_tally else None
        result = {
            "time": datetime.now().isoformat(timespec="seconds"),
            "frames": captured,
            "disease": disease_best,
            "disease_counts": dict(disease_tally),
            "ripeness": ripeness_best,
            "ripeness_counts": dict(ripeness_tally),
            "confidence": round(best_conf, 3),
        }
        result["image"] = self._save(result, best_frame)
        self._set(state="idle", message="scan complete", last_result=result)
        if disease_best:
            self._email_alert(result)

    def _save(self, result: dict, frame) -> str:
        folder = config.STORAGE_DIR / "farmmonitor"
        folder.mkdir(parents=True, exist_ok=True)
        stamp = str(int(time.time()))
        (folder / f"{stamp}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        if frame is not None and cv2 is not None:
            cv2.imwrite(str(folder / f"{stamp}.jpg"), frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            return f"/storage_img/farmmonitor/{stamp}.jpg"
        return ""

    def _email_alert(self, result: dict) -> None:
        if not notify.smtp_ready(self.app_config):
            return
        subject = f"AIgriculture: possible {result['disease']} detected"
        body = (f"FarmMonitor scan at {result['time']} flagged: {result['disease']} "
                f"(confidence {result['confidence']:.0%}). Ripeness: {result['ripeness'] or 'n/a'}.")
        img = config.STORAGE_DIR / "farmmonitor" / Path(result.get("image", "")).name
        notify.send_email(self.app_config, subject, body,
                          attachments=[str(img)] if img.is_file() else None)
