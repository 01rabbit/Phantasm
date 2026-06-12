from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

import cv2

LOG = logging.getLogger(__name__)


@dataclass
class CameraRuntimeState:
    ready: bool = False
    active_backend: str = "none"
    last_error: str | None = None
    backend_warnings: list[str] = field(default_factory=list)
    resolution: dict[str, int] = field(
        default_factory=lambda: {"width": 0, "height": 0}
    )
    fps_target: int = 0
    last_frame_at: float | None = None
    frames_yielded: int = 0


class CameraFrameSource:
    """Camera capture wrapper with Picamera2-first backend selection.

    Backend open/read/release operations are serialized through an internal
    re-entrant lock.  Runtime state is observational and should not be used as
    a cross-thread synchronization primitive by callers.
    """

    def __init__(self, *, frame_size: tuple[int, int], fps: int = 5) -> None:
        self.frame_size = frame_size
        self.fps = fps
        self.cap: Any | None = None
        self.picam2: Any | None = None
        self.backend = "none"
        self.last_error: str | None = None
        self._last_open_attempt_at = 0.0
        self._open_retry_seconds = 2.0
        self._lock = threading.RLock()
        self._first_frame_logged = False
        self.source_pixel_format = "unknown"
        self._last_rgb_to_bgr_applied = False
        self.state = CameraRuntimeState(
            resolution={"width": frame_size[0], "height": frame_size[1]},
            fps_target=fps,
        )

    def open(self) -> None:
        with self._lock:
            self._open_locked()

    def _open_locked(self) -> None:
        now = time.time()
        if self.backend in {"picamera2", "opencv"}:
            return
        if (
            self.backend == "unavailable"
            and (now - self._last_open_attempt_at) < self._open_retry_seconds
        ):
            return
        self._last_open_attempt_at = now

        if self._open_picamera2():
            return
        if self._open_opencv():
            return

        self.backend = "unavailable"
        self.state.active_backend = "unavailable"
        self.state.ready = False
        if self.last_error is None:
            self.last_error = "camera backend unavailable"
        self.state.last_error = self.last_error
        LOG.error("Camera initialization failed: %s", self.last_error)

    def _open_picamera2(self) -> bool:
        try:
            from picamera2 import Picamera2  # type: ignore[import-not-found]
        except Exception as exc:
            self.last_error = f"Picamera2 import failed: {exc}"
            self.state.backend_warnings.append(self.last_error)
            LOG.warning("%s", self.last_error)
            return False

        try:
            self.picam2 = Picamera2()
            config = self.picam2.create_video_configuration(
                main={"size": self.frame_size, "format": "RGB888"},
                controls={"FrameDurationLimits": (200000, 333333)},
            )
            self.picam2.configure(config)
            self.picam2.start()
            self.backend = "picamera2"
            self.source_pixel_format = "RGB888"
            self.last_error = None
            self.state.active_backend = "picamera2"
            self.state.last_error = None
            LOG.info(
                "Camera backend selected: picamera2 (%dx%d @ ~%dfps)",
                self.frame_size[0],
                self.frame_size[1],
                self.fps,
            )
            return True
        except Exception as exc:
            self.last_error = f"Picamera2 startup failed: {exc}"
            self.state.backend_warnings.append(self.last_error)
            LOG.error("%s", self.last_error)
            self._release_picamera2()
            return False

    def _open_opencv(self) -> bool:
        try:
            self.cap = cv2.VideoCapture(0)
            if self.cap is None or not self.cap.isOpened():
                self.last_error = "OpenCV VideoCapture(0) open failed"
                self.state.backend_warnings.append(self.last_error)
                LOG.error("%s", self.last_error)
                self._release_opencv()
                return False
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.frame_size[0])
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.frame_size[1])
            self.cap.set(cv2.CAP_PROP_FPS, float(self.fps))
            self.backend = "opencv"
            self.source_pixel_format = "BGR"
            self.last_error = None
            self.state.active_backend = "opencv"
            self.state.last_error = None
            LOG.info(
                "Camera backend selected: opencv (%dx%d @ ~%dfps)",
                self.frame_size[0],
                self.frame_size[1],
                self.fps,
            )
            return True
        except Exception as exc:
            self.last_error = f"OpenCV startup failed: {exc}"
            self.state.backend_warnings.append(self.last_error)
            LOG.error("%s", self.last_error)
            self._release_opencv()
            return False

    def read(self):
        with self._lock:
            self._open_locked()
            return self._read_locked()

    def _read_locked(self):
        if self.backend == "picamera2":
            if self.picam2 is None:
                self.last_error = "Picamera2 backend lost"
                return False, None
            try:
                frame_for_jpeg = self.picam2.capture_array("main")
                frame_encoded = self._prepare_frame_for_jpeg(
                    frame_for_jpeg, source_format=self.source_pixel_format
                )
                self.last_error = None
                self.state.last_error = None
                self.state.active_backend = "picamera2"
                self.state.last_frame_at = time.time()
                self.state.ready = True
                self._log_first_frame_details(frame_encoded)
                return True, frame_encoded
            except Exception as exc:
                self.last_error = f"Picamera2 frame capture failed: {exc}"
                self.state.last_error = self.last_error
                self.state.ready = False
                LOG.error("%s", self.last_error)
                return False, None

        if self.backend == "opencv":
            if self.cap is None:
                self.last_error = "OpenCV backend lost"
                return False, None
            ok, frame = self.cap.read()
            if not ok:
                self.last_error = "OpenCV frame read failed"
                self.state.last_error = self.last_error
                self.state.ready = False
                LOG.error("%s", self.last_error)
                return False, None
            self.last_error = None
            self.state.last_error = None
            self.state.active_backend = "opencv"
            self.state.last_frame_at = time.time()
            self.state.ready = True
            self._log_first_frame_details(frame)
            return True, frame

        return False, None

    def mark_frame_yielded(self) -> None:
        with self._lock:
            self.state.frames_yielded += 1
            self.state.last_frame_at = time.time()
            self.state.ready = True
            self.state.last_error = None
            if self.state.active_backend not in {"picamera2", "opencv", "stream"}:
                self.state.active_backend = (
                    self.backend
                    if self.backend in {"picamera2", "opencv"}
                    else "stream"
                )

    def close(self) -> None:
        with self._lock:
            cleanup_error: str | None = None
            try:
                self._release_picamera2()
            except Exception as exc:
                cleanup_error = f"Picamera2 cleanup failed: {exc}"
                LOG.error("%s", cleanup_error)
            try:
                self._release_opencv()
            except Exception as exc:
                msg = f"OpenCV cleanup failed: {exc}"
                cleanup_error = f"{cleanup_error}; {msg}" if cleanup_error else msg
                LOG.error("%s", msg)
            self.backend = "none"
            self.source_pixel_format = "unknown"
            self.state.active_backend = "none"
            self.state.ready = False
            self.state.last_frame_at = None
            self.state.last_error = cleanup_error
            self._first_frame_logged = False
            self._last_rgb_to_bgr_applied = False

    def release(self) -> None:
        self.close()

    def status(self) -> dict[str, Any]:
        with self._lock:
            ready_now = self.state.ready
            if self.state.last_frame_at is not None:
                ready_now = (
                    ready_now and (time.time() - self.state.last_frame_at) <= 30.0
                )
            backend = self.state.active_backend
            if (
                ready_now
                and backend in {"none", "unavailable"}
                and self.state.frames_yielded > 0
            ):
                backend = "stream"
            return {
                "backend": backend,
                "ready": ready_now,
                "last_error": self.state.last_error,
                "backend_warnings": list(self.state.backend_warnings[-4:]),
                "resolution": {
                    "width": self.frame_size[0],
                    "height": self.frame_size[1],
                },
                "fps_target": self.fps,
                "last_frame_at": self.state.last_frame_at,
                "frames_yielded": self.state.frames_yielded,
                "source_pixel_format": self.source_pixel_format,
                "rgb_to_bgr_applied": self._last_rgb_to_bgr_applied,
            }

    def _prepare_frame_for_jpeg(self, frame, *, source_format: str):
        # Hardware note: on some Raspberry Pi Picamera2 paths, RGB888 frames are
        # already suitable for OpenCV JPEG encode without channel swap.
        if source_format in {"RGB888", "RGB"}:
            self._last_rgb_to_bgr_applied = False
            return frame
        if source_format in {"XRGB8888", "ARGB8888", "RGBA"}:
            self._last_rgb_to_bgr_applied = True
            return cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)
        if source_format in {"BGR", "BGR888"}:
            self._last_rgb_to_bgr_applied = False
            return frame
        LOG.warning("Unknown source pixel format for JPEG prep: %s", source_format)
        self._last_rgb_to_bgr_applied = False
        return frame

    def _log_first_frame_details(self, frame) -> None:
        if self._first_frame_logged:
            return
        self._first_frame_logged = True
        LOG.info(
            "Camera first frame: backend=%s source_format=%s shape=%s dtype=%s rgb_to_bgr=%s",
            self.state.active_backend,
            self.source_pixel_format,
            getattr(frame, "shape", None),
            getattr(frame, "dtype", None),
            self._last_rgb_to_bgr_applied,
        )

    def _release_picamera2(self) -> None:
        if self.picam2 is None:
            return
        try:
            self.picam2.stop()
        except Exception:
            pass
        try:
            self.picam2.close()
        except Exception:
            pass
        self.picam2 = None

    def _release_opencv(self) -> None:
        if self.cap is None:
            return
        try:
            self.cap.release()
        except Exception:
            pass
        self.cap = None
