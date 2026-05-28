"""USB / V4L2 camera backend (OpenCV)."""

from __future__ import annotations

from typing import Optional, Tuple

from .base import CameraError, CameraSource, Frame

try:
    import cv2
except ImportError as e:  # pragma: no cover
    raise CameraError("opencv-python is required for USB cameras") from e


class UsbCameraSource(CameraSource):
    def __init__(self, target: str, width: int = 640, height: int = 480, fps: int = 15):
        super().__init__(target, width, height, fps)
        # OpenCV accepts either an index (0) or a device path (/dev/video0).
        self._index = int(target) if str(target).isdigit() else target
        self._cap: Optional["cv2.VideoCapture"] = None

    def open(self) -> None:
        cap = cv2.VideoCapture(self._index)
        if not cap.isOpened():
            raise CameraError(f"could not open USB camera {self._index!r}")
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        cap.set(cv2.CAP_PROP_FPS, self.fps)
        # Keep the grab buffer shallow so the dashboard shows live, not stale, frames.
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self._cap = cap

    def read(self) -> Tuple[bool, Optional[Frame]]:
        if self._cap is None:
            return False, None
        ok, frame = self._cap.read()
        return bool(ok), frame if ok else None

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
