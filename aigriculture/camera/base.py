"""Camera abstraction.

One interface, three backends: Pi CSI, USB/V4L2, and network (RTSP/HTTP).
The backend is chosen from a --camera spec string so users pick whatever
hardware they own without touching code:

    csi:0            -> Pi camera 0 (libcamera / picamera2)
    /dev/video0      -> USB webcam (OpenCV/V4L2)
    0                -> USB webcam by index
    rtsp://host/...  -> network/IP camera
    http://host/...  -> MJPEG/HTTP network camera

Every backend returns frames as BGR numpy arrays (OpenCV convention) so the
inference layer never needs to know where the frame came from.
"""

from __future__ import annotations

import abc
from typing import Optional, Tuple

import numpy as np

Frame = np.ndarray  # HxWx3, BGR, uint8


class CameraSource(abc.ABC):
    """A video source that yields BGR frames."""

    def __init__(self, spec: str, width: int = 640, height: int = 480, fps: int = 15):
        self.spec = spec
        self.width = width
        self.height = height
        self.fps = fps

    @abc.abstractmethod
    def open(self) -> None:
        """Acquire the device. Raise CameraError if it cannot be opened."""

    @abc.abstractmethod
    def read(self) -> Tuple[bool, Optional[Frame]]:
        """Return (ok, frame). ok is False when no frame is available."""

    @abc.abstractmethod
    def release(self) -> None:
        """Release the device. Safe to call more than once."""

    def __enter__(self) -> "CameraSource":
        self.open()
        return self

    def __exit__(self, *exc) -> None:
        self.release()


class CameraError(RuntimeError):
    """Raised when a camera source cannot be opened or read."""


def parse_camera_spec(spec: str) -> Tuple[str, str]:
    """Map a --camera string to a (kind, target) pair.

    kind is one of: "csi", "usb", "network".
    """
    s = (spec or "").strip()
    if not s:
        raise CameraError("empty camera spec")
    low = s.lower()
    if low.startswith(("rtsp://", "http://", "https://", "rtmp://")):
        return "network", s
    if low.startswith("csi:") or low == "csi":
        return "csi", s.split(":", 1)[1] if ":" in s else "0"
    if s.startswith("/dev/video") or s.isdigit():
        return "usb", s
    # Bare hostnames/paths fall through to network so IP cams "just work".
    return "network", s


def open_camera(spec: str, width: int = 640, height: int = 480, fps: int = 15) -> CameraSource:
    """Build and open the right CameraSource for the given spec."""
    kind, target = parse_camera_spec(spec)
    if kind == "csi":
        from .picamera import PiCameraSource
        cam: CameraSource = PiCameraSource(target, width, height, fps)
    elif kind == "usb":
        from .usb import UsbCameraSource
        cam = UsbCameraSource(target, width, height, fps)
    else:
        from .network import NetworkCameraSource
        cam = NetworkCameraSource(target, width, height, fps)
    cam.open()
    return cam
