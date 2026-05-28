"""Raspberry Pi CSI camera backend (picamera2 / libcamera)."""

from __future__ import annotations

from typing import Optional, Tuple

from .base import CameraError, CameraSource, Frame

try:
    from picamera2 import Picamera2
    _AVAILABLE = True
except ImportError:
    Picamera2 = None  # type: ignore
    _AVAILABLE = False

try:
    import cv2
except ImportError:  # pragma: no cover
    cv2 = None  # type: ignore


class PiCameraSource(CameraSource):
    def __init__(self, target: str = "0", width: int = 640, height: int = 480, fps: int = 15):
        super().__init__(f"csi:{target}", width, height, fps)
        self._num = int(target) if str(target).isdigit() else 0
        self._cam = None

    def open(self) -> None:
        if not _AVAILABLE:
            raise CameraError(
                "picamera2 is not installed — use a USB (/dev/videoN) or network camera instead"
            )
        cam = Picamera2(self._num)
        cfg = cam.create_video_configuration(
            main={"size": (self.width, self.height), "format": "RGB888"}
        )
        cam.configure(cfg)
        cam.start()
        self._cam = cam

    def read(self) -> Tuple[bool, Optional[Frame]]:
        if self._cam is None:
            return False, None
        rgb = self._cam.capture_array()
        # picamera2 gives RGB; convert to BGR so all backends look identical downstream.
        if cv2 is not None:
            return True, cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        return True, rgb[:, :, ::-1]

    def release(self) -> None:
        if self._cam is not None:
            try:
                self._cam.stop()
                self._cam.close()
            finally:
                self._cam = None
