"""Network / IP camera backend (RTSP or HTTP/MJPEG, via OpenCV)."""

from __future__ import annotations

import time
from typing import Optional, Tuple

from .base import CameraError, CameraSource, Frame

try:
    import cv2
except ImportError as e:  # pragma: no cover
    raise CameraError("opencv-python is required for network cameras") from e


class NetworkCameraSource(CameraSource):
    """Reads an RTSP/HTTP stream and transparently reconnects if it drops."""

    def __init__(self, url: str, width: int = 640, height: int = 480, fps: int = 15):
        super().__init__(url, width, height, fps)
        self.url = url
        self._cap: Optional["cv2.VideoCapture"] = None
        self._last_reconnect = 0.0

    def open(self) -> None:
        cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
        if not cap.isOpened():
            raise CameraError(f"could not open network camera {self.url!r}")
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self._cap = cap

    def _reconnect(self) -> None:
        # Throttle reconnects so a dead camera can't spin the CPU.
        now = time.monotonic()
        if now - self._last_reconnect < 2.0:
            return
        self._last_reconnect = now
        self.release()
        try:
            self.open()
        except CameraError:
            self._cap = None

    def read(self) -> Tuple[bool, Optional[Frame]]:
        if self._cap is None:
            self._reconnect()
            return False, None
        ok, frame = self._cap.read()
        if not ok:
            self._reconnect()
            return False, None
        return True, frame

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
