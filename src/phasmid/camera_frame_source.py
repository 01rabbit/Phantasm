from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

import cv2

from .config import (
    camera_denoise,
    camera_focus_mode,
    camera_lock_white_balance,
    camera_max_exposure_us,
    camera_sharpness,
)

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
        #: What was done about focus, reported in `status()`. A lens
        #: parked at the wrong distance shows up in no single score, only
        #: in every score at once.
        self.focus_mode = "unset"
        #: Which of the tuning controls the module actually accepted. Reported
        #: in `status()`, because "the camera ignored half of this" is
        #: otherwise indistinguishable from "the camera is set up correctly".
        self.applied_controls: list[str] = []
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
            camera_controls = self._build_controls()
            config = self.picam2.create_video_configuration(
                main={"size": self.frame_size, "format": "RGB888"},
                controls=camera_controls,
            )
            self.picam2.configure(config)
            self.picam2.start()
            self._settle_white_balance()
            self.backend = "picamera2"
            self.source_pixel_format = "RGB888"
            self.last_error = None
            self.state.active_backend = "picamera2"
            self.state.last_error = None
            LOG.info(
                "Camera backend selected: picamera2 (%dx%d @ ~%dfps, focus=%s, "
                "applied=%s)",
                self.frame_size[0],
                self.frame_size[1],
                self.fps,
                self.focus_mode,
                ",".join(sorted(self.applied_controls)) or "none",
            )
            return True
        except Exception as exc:
            self.last_error = f"Picamera2 startup failed: {exc}"
            self.state.backend_warnings.append(self.last_error)
            LOG.error("%s", self.last_error)
            self._release_picamera2()
            return False

    def _focus_controls(self, supported: dict, applied: list[str]) -> dict[str, Any]:
        """Put the lens where the object is, and keep it there.

        The Camera Module 3 family (`imx708`) has a motorised lens, and
        picamera2 leaves it wherever it powered up unless told otherwise -
        which, for a camera pointed at something on a desk, is the wrong
        distance. Nothing reports that. An out-of-focus frame is not an error;
        it is a frame with hardly any corners in it, so the cue reads as an
        object that will not bind and will not match, and every symptom of a
        misplaced lens looks like a symptom of something else.

        Three controls, not one, because autofocus on its own still gets it
        wrong here:

        * `AfMode` - engage the lens at all.
        * `AfSpeed` - an object is held up for a couple of seconds, and a lens
          still travelling when the capture fires is a lens in the wrong place.
        * `AfWindows` - focus on the middle, where the object is presented.
          Metered across the whole frame, the algorithm is as likely to lock
          onto the desk or the far wall, both of which are more of the picture
          than the object is.

        `PHASMID_CAMERA_FOCUS` overrides: `continuous` (default), `auto` for a
        single sweep, `off` to leave the lens alone, or a number to park it at
        that many dioptres - 0 is infinity, 5.0 is roughly 20 cm.
        """
        setting = camera_focus_mode()
        if setting == "off":
            self.focus_mode = "off (lens left alone)"
            return {}

        if "AfMode" not in supported:
            self.focus_mode = "fixed lens"
            return {}

        try:
            from libcamera import controls as libcamera_controls  # type: ignore
        except Exception as exc:  # pragma: no cover - depends on the host stack
            self.focus_mode = "unavailable"
            LOG.debug("focus controls unavailable: %s", exc)
            return {}

        try:
            position = float(setting)
        except ValueError:
            position = None

        if position is not None:
            self.focus_mode = f"manual at {position} dioptres"
            applied.append("focus-manual")
            return {
                "AfMode": libcamera_controls.AfModeEnum.Manual,
                "LensPosition": position,
            }

        controls: dict[str, Any] = {}
        if setting == "auto":
            self.focus_mode = "auto (single sweep)"
            controls["AfMode"] = libcamera_controls.AfModeEnum.Auto
        else:
            self.focus_mode = "continuous"
            controls["AfMode"] = libcamera_controls.AfModeEnum.Continuous
        applied.append(f"focus-{self.focus_mode.split()[0]}")

        if "AfSpeed" in supported:
            controls["AfSpeed"] = libcamera_controls.AfSpeedEnum.Fast
            applied.append("focus-fast")

        window = self._centre_focus_window()
        if window and "AfWindows" in supported and "AfMetering" in supported:
            controls["AfMetering"] = libcamera_controls.AfMeteringEnum.Windows
            controls["AfWindows"] = [window]
            applied.append("focus-centre-window")

        return controls

    def _centre_focus_window(self) -> tuple[int, int, int, int] | None:
        """The middle half of the sensor, in the units `AfWindows` wants.

        Expressed against `ScalerCropMaximum` because focus windows are in
        sensor coordinates, not output-image ones, and the two are not the same
        on a camera that crops.
        """
        try:
            properties = self.picam2.camera_properties if self.picam2 else {}
            crop = properties.get("ScalerCropMaximum")
            if not crop:
                return None
            x, y, width, height = crop
            if width <= 0 or height <= 0:
                return None
            return (
                int(x + width * 0.25),
                int(y + height * 0.25),
                int(width * 0.5),
                int(height * 0.5),
            )
        except Exception as exc:  # pragma: no cover - depends on the host stack
            LOG.debug("focus window unavailable: %s", exc)
            return None

    def refocus(self, settle_seconds: float = 1.2) -> bool:
        """Ask for a focus sweep now and wait for the lens to arrive.

        Called before a capture that is about to become a template. Continuous
        autofocus is generally in the right place, but "generally" is doing a
        lot of work at the one moment that gets written to disk and has to keep
        matching afterwards.
        """
        if self.picam2 is None:
            return False
        try:
            from libcamera import controls as libcamera_controls  # type: ignore

            if "AfTrigger" not in self._supported_controls():
                return False
            self.picam2.set_controls(
                {"AfTrigger": libcamera_controls.AfTriggerEnum.Start}
            )
            time.sleep(settle_seconds)
            return True
        except Exception as exc:  # pragma: no cover - depends on the host stack
            LOG.debug("refocus skipped: %s", exc)
            return False

    def _supported_controls(self) -> dict:
        """What this module actually exposes, asked rather than assumed.

        Camera modules differ: a fixed-focus one has no `AfMode` at all, and a
        pipeline without the draft controls has no `NoiseReductionMode`. Every
        control below is offered only if it is in here, so an unfamiliar module
        loses the tuning rather than failing to open.
        """
        try:
            return dict(self.picam2.camera_controls) if self.picam2 else {}
        except Exception as exc:  # pragma: no cover - depends on the host stack
            LOG.debug("camera control enumeration failed: %s", exc)
            return {}

    def _build_controls(self) -> dict[str, Any]:
        """Everything this camera is asked to do, in one place.

        The camera was previously opened with a single control -
        `FrameDurationLimits` - and nothing else. That left the lens wherever it
        powered up, the shutter free to run to 200 ms, the ISP free to denoise
        away the detail the cue is built from, and white balance free to drift
        under the grayscale conversion. None of those appear as errors. They
        appear as an object that will not bind and will not match, which is
        where several days went.
        """
        supported = self._supported_controls()
        controls: dict[str, Any] = {}
        applied: list[str] = []

        # Frame duration bounds the shutter, and the shutter bounds motion
        # blur. The lower bound stays loose so auto-exposure can still run the
        # sensor fast in good light.
        ceiling = camera_max_exposure_us()
        if "FrameDurationLimits" in supported:
            controls["FrameDurationLimits"] = (max(1000, ceiling // 4), ceiling)
            applied.append("exposure-ceiling")

        controls.update(self._focus_controls(supported, applied))
        controls.update(self._detail_controls(supported, applied))
        controls.update(self._metering_controls(supported, applied))

        self.applied_controls = applied
        return controls

    def _detail_controls(self, supported: dict, applied: list[str]) -> dict[str, Any]:
        """Keep the fine structure the cue is made of.

        Denoising smooths small high-frequency detail - print, weave, the edge
        of a label - which is the same detail a corner detector lives on. The
        picture looks cleaner and describes less. Sharpening is the other half:
        FAST decides a corner from local contrast, so raising edge contrast
        raises the keypoint count on the same object.
        """
        controls: dict[str, Any] = {}

        wanted = camera_denoise()
        if wanted != "fast" and "NoiseReductionMode" in supported:
            try:
                from libcamera import controls as libcamera_controls  # type: ignore

                modes = libcamera_controls.draft.NoiseReductionModeEnum
                controls["NoiseReductionMode"] = (
                    modes.Off if wanted == "off" else modes.Minimal
                )
                applied.append(f"denoise-{wanted}")
            except Exception as exc:  # pragma: no cover
                LOG.debug("noise reduction control unavailable: %s", exc)

        sharpness = camera_sharpness()
        if "Sharpness" in supported and sharpness != 1.0:
            controls["Sharpness"] = sharpness
            applied.append(f"sharpness-{sharpness}")

        return controls

    def _metering_controls(self, supported: dict, applied: list[str]) -> dict[str, Any]:
        """Expose for the object, not for the desk around it.

        The object is presented in the middle of the frame and the rest is
        whatever the camera happens to be pointed at. Averaged over the whole
        view, a dark desk pushes exposure up until the object washes out, and a
        bright one pushes it down until the object goes black. Either way the
        thing being measured is the only part of the frame that matters and the
        only part not being metered.
        """
        controls: dict[str, Any] = {}
        if "AeMeteringMode" not in supported:
            return controls
        try:
            from libcamera import controls as libcamera_controls  # type: ignore

            controls["AeMeteringMode"] = (
                libcamera_controls.AeMeteringModeEnum.CentreWeighted
            )
            applied.append("centre-weighted-metering")
        except Exception as exc:  # pragma: no cover
            LOG.debug("metering control unavailable: %s", exc)
        return controls

    def _settle_white_balance(self) -> None:
        """Let auto white balance converge, then hold it there.

        Grayscale is a weighted sum of the three channels, so every change the
        AWB algorithm makes is a global change to what ORB sees - the same
        object described slightly differently one second to the next. On a NoIR
        sensor the red channel carries infrared the algorithm was not designed
        for, so it hunts more than usual. Letting it settle and then freezing
        the gains removes the drift without hard-coding a colour temperature
        for a room nobody has seen.
        """
        if not camera_lock_white_balance() or self.picam2 is None:
            return
        try:
            if "ColourGains" not in self._supported_controls():
                return
            time.sleep(1.0)
            gains = self.picam2.capture_metadata().get("ColourGains")
            if not gains:
                return
            self.picam2.set_controls({"AwbEnable": False, "ColourGains": tuple(gains)})
            self.applied_controls.append("awb-locked")
            LOG.info(
                "White balance locked at gains %s", tuple(round(g, 3) for g in gains)
            )
        except Exception as exc:  # pragma: no cover - depends on the host stack
            LOG.debug("white balance lock skipped: %s", exc)

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
                "focus_mode": self.focus_mode,
                "applied_controls": list(self.applied_controls),
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
