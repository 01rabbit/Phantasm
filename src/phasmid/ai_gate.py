import logging
import os
import threading
import time
from collections.abc import Iterator
from typing import Any, cast

import cv2
import numpy as np

from . import strings as text
from .camera_frame_source import CameraFrameSource
from .config import (
    STATE_BLOB_NAME,
    STATE_KEY_NAME,
    cue_debug_overlay_enabled,
    cue_good_match_ratio,
    cue_inlier_ratio,
    cue_lowe_ratio,
    cue_ransac_reprojection_px,
    debug_enabled,
    dummy_fallback_threshold,
    experimental_object_model_enabled,
    recognition_mode,
    state_dir,
    true_unlock_threshold,
)
from .local_state_crypto import LocalStateCipher
from .object_cue_matcher import ObjectCueMatcher
from .object_cue_store import ObjectCueStore
from .object_gate import ObjectGate

LOG = logging.getLogger(__name__)


class AIGate:
    """Object-cue orchestrator with one capture thread and lock-guarded state.

    The frame generator may run on a background thread.  Shared match state and
    reference data are mutated only while holding ``self.lock``; callers should
    use the public methods instead of reading those fields as synchronization
    primitives.
    """

    # Legacy internal identifiers are retained for vault compatibility only.
    # They must never be emitted to UI, API responses, overlays, CLI output,
    # default logs, documentation examples, or user-visible errors.
    MODES = ("dummy", "secret")
    AUTH_TOKENS = {
        "dummy": "reference_dummy_matched",
        "secret": "reference_secret_matched",
    }
    MATCH_NONE = "none"
    MATCH_AMBIGUOUS = "ambiguous"
    MIN_REFERENCE_KEYPOINTS = 60
    MIN_FRAME_DESCRIPTORS = 10
    MIN_GOOD_MATCHES = 50
    MIN_INLIERS = 30
    FRAME_SIZE = (320, 240)
    MATCH_HISTORY_FRAMES = 5
    MATCH_HISTORY_REQUIRED = 3
    REFERENCE_CAPTURE_SAMPLES = 3
    TARGET_FPS = 4
    MODE_STRICT = "strict"
    MODE_COERCION_SAFE = "coercion_safe"
    MODE_DEMO = "demo"

    def __init__(self, reference_dir: str | None = None) -> None:
        self._stop_event = threading.Event()
        self.lock = threading.Lock()
        self.latest_frame: Any | None = None
        # The empty scene, held only between a capture_scene() and the
        # capture_reference() that consumes it. Never persisted: it describes
        # where the operator happened to be standing, not a credential.
        self.scene_frame: Any | None = None
        # generate_frames() is called by two independent, concurrent
        # consumers: the always-on background thread that keeps object-cue
        # matching live for the TUI, and a fresh call per WebUI /video_feed
        # request. Both read the one shared CameraFrameSource. Counted here
        # so the hardware is only released when the last consumer's
        # generator exits - see the note on generate_frames() below.
        self._camera_consumers = 0

        self.reference_dir = reference_dir or state_dir()
        os.makedirs(self.reference_dir, mode=0o700, exist_ok=True)
        try:
            os.chmod(self.reference_dir, 0o700)
        except OSError as exc:
            LOG.debug("object cue directory permission update failed: %s", exc)
        self.state_blob_path = os.path.join(self.reference_dir, STATE_BLOB_NAME)
        self.state_key_path = os.path.join(self.reference_dir, STATE_KEY_NAME)
        self.state_cipher = LocalStateCipher(
            state_key_path=self.state_key_path,
            aad=self._template_aad(self.state_blob_path),
        )
        self.store = ObjectCueStore(
            modes=self.MODES,
            state_blob_path=self.state_blob_path,
            state_cipher=self.state_cipher,
            empty_reference=self._empty_reference,
            state_to_arrays=self._state_to_arrays,
            reference_from_arrays=self._reference_state_from_arrays,
        )

        self.object_detected = False
        self.last_match_mode = self.MATCH_NONE
        self.match_states = {mode: False for mode in self.MODES}
        self.match_history: list[tuple[str, ...]] = []
        self.latest_gate_results: dict[str, Any] = {}

        self.matcher = ObjectCueMatcher(
            min_reference_keypoints=self.MIN_REFERENCE_KEYPOINTS,
            min_frame_descriptors=self.MIN_FRAME_DESCRIPTORS,
            min_good_matches=self.MIN_GOOD_MATCHES,
            min_inliers=self.MIN_INLIERS,
            min_good_match_ratio=cue_good_match_ratio(),
            min_inlier_ratio=cue_inlier_ratio(),
            lowe_ratio=cue_lowe_ratio(),
            ransac_reprojection=cue_ransac_reprojection_px(),
        )
        self.experimental_object_model_enabled = experimental_object_model_enabled()
        self.object_gate = ObjectGate()
        self.camera = CameraFrameSource(frame_size=self.FRAME_SIZE, fps=self.TARGET_FPS)

        self.reference_data = {mode: self._empty_reference() for mode in self.MODES}
        self._load_references()

        self._thread: threading.Thread | None = None

    def _empty_reference(self) -> dict[str, Any]:
        return self.matcher.empty_reference()

    def _validate_mode(self, mode: str) -> None:
        if mode not in self.MODES:
            raise ValueError("unsupported local entry")

    def _reference_state_from_image(self, image: Any) -> dict[str, Any] | None:
        return cast(
            dict[str, Any] | None, self.matcher.reference_state_from_image(image)
        )

    def _to_gray(self, image: Any) -> Any:
        return self.matcher.to_gray(image)

    def _reference_state_from_arrays(
        self, des: Any, kp_data: Any, shape: Any
    ) -> dict[str, Any]:
        state = cast(
            dict[str, Any],
            self.matcher.reference_state_from_arrays(des, kp_data, shape),
        )
        if state["des"] is not None:
            state["path"] = self.state_blob_path
        return state

    def _load_references(self) -> None:
        with self.lock:
            self.reference_data = self.store.load()

    def _match_reference_state(
        self, ref_state: dict[str, Any], frame_gray: Any
    ) -> dict[str, object] | None:
        return cast(
            dict[str, object] | None,
            self.matcher.match_reference_state(ref_state, frame_gray),
        )

    def _match_descriptors(
        self, ref_state: dict[str, Any], kp: Any, des: Any
    ) -> dict[str, object] | None:
        return cast(
            dict[str, object] | None,
            self.matcher.match_descriptors(ref_state, kp, des),
        )

    def _references_too_similar(
        self, mode: str, candidate_state: dict[str, Any]
    ) -> bool:
        other_mode = "secret" if mode == "dummy" else "dummy"
        other_state = self.reference_data[other_mode]
        if other_state["des"] is None:
            return False

        return (
            self._match_descriptors(
                candidate_state, other_state["kp"], other_state["des"]
            )
            is not None
        )

    def _state_to_arrays(self, state: dict[str, Any]) -> dict[str, np.ndarray]:
        kp_data = np.array(
            [
                [
                    point.pt[0],
                    point.pt[1],
                    point.size,
                    point.angle,
                    point.response,
                    point.octave,
                    point.class_id,
                ]
                for point in state["kp"]
            ],
            dtype=np.float32,
        )
        return {
            "des": state["des"],
            "kp": kp_data,
            "shape": np.array(state["shape"], dtype=np.int32),
        }

    def _read_reference_blob(self) -> dict[str, dict[str, object | None]]:
        return self.store.load()

    def _write_reference_blob(
        self, references: dict[str, dict[str, object | None]]
    ) -> None:
        self.store.save(references)

    def _encrypt_template(self, plaintext: bytes, path: str) -> bytes:
        return self.state_cipher.encrypt(plaintext)

    def _read_encrypted_template(self, path: str) -> bytes:
        with open(path, "rb") as handle:
            data = handle.read()
        return self.state_cipher.decrypt(
            data,
            too_short_message="reference template is too short",
            auth_failed_message="reference template authentication failed",
        )

    def _state_encryption_key(self) -> bytes:
        return self.state_cipher.encryption_key()

    def _load_or_create_local_state_key(self) -> bytes:
        return self.state_cipher._load_or_create_local_state_key()

    def _template_aad(self, path: str) -> bytes:
        return f"phasmid-reference-state:{os.path.basename(path)}".encode("utf-8")

    def _update_match_result(
        self, matches: dict[str, dict[str, object] | None]
    ) -> None:
        active_modes = [mode for mode, result in matches.items() if result is not None]
        self.match_history.append(tuple(active_modes))
        self.match_history = self.match_history[-self.MATCH_HISTORY_FRAMES :]

        stable_modes = []
        for mode in self.MODES:
            count = sum(1 for active in self.match_history if mode in active)
            if count >= self.MATCH_HISTORY_REQUIRED:
                stable_modes.append(mode)

        active_modes = stable_modes
        if not active_modes:
            self.last_match_mode = self.MATCH_NONE
            self.object_detected = False
            self.match_states = {mode: False for mode in self.MODES}
            return

        if len(active_modes) > 1:
            self.last_match_mode = self.MATCH_AMBIGUOUS
            self.object_detected = False
            self.match_states = {mode: True for mode in active_modes}
            for mode in self.MODES:
                if mode not in active_modes:
                    self.match_states[mode] = False
            return

        matched_mode = active_modes[0]
        self.last_match_mode = matched_mode
        self.object_detected = True
        self.match_states = {mode: mode == matched_mode for mode in self.MODES}

    def _update_match_result_from_gate_results(self, results: dict[str, Any]) -> None:
        if any(result.state == "ambiguous" for result in results.values()):
            self.latest_gate_results = results
            self.last_match_mode = self.MATCH_AMBIGUOUS
            self.object_detected = False
            self.match_states = {mode: False for mode in self.MODES}
            self.match_history = []
            return

        active_modes = [
            mode for mode, result in results.items() if result.state == "accepted"
        ]
        self.match_history.append(tuple(active_modes))
        self.match_history = self.match_history[-self.MATCH_HISTORY_FRAMES :]

        stable_modes = []
        stable_counts = {}
        for mode in self.MODES:
            count = sum(1 for active in self.match_history if mode in active)
            stable_counts[mode] = count
            if count >= self.MATCH_HISTORY_REQUIRED:
                stable_modes.append(mode)

        self.latest_gate_results = {
            mode: result.with_stable_frames(stable_counts[mode])
            for mode, result in results.items()
        }

        if not stable_modes:
            self.last_match_mode = self.MATCH_NONE
            self.object_detected = False
            self.match_states = {mode: False for mode in self.MODES}
            return

        if len(stable_modes) > 1:
            self.last_match_mode = self.MATCH_AMBIGUOUS
            self.object_detected = False
            self.match_states = {mode: mode in stable_modes for mode in self.MODES}
            return

        matched_mode = stable_modes[0]
        self.last_match_mode = matched_mode
        self.object_detected = True
        self.match_states = {mode: mode == matched_mode for mode in self.MODES}

    def sequence_for_mode(self, mode: str, length: int = 1) -> list[str]:
        self._validate_mode(mode)
        return [self.AUTH_TOKENS[mode]] * length

    def get_auth_sequence(self, length: int = 1) -> list[str]:
        current_mode = recognition_mode()
        confidence = self._recognition_confidence()
        true_threshold = true_unlock_threshold()
        fallback_threshold = dummy_fallback_threshold()

        if self.last_match_mode in self.AUTH_TOKENS and confidence >= true_threshold:
            return self.sequence_for_mode(self.last_match_mode, length=length)

        if current_mode == self.MODE_COERCION_SAFE:
            return self.sequence_for_mode(self.MODES[0], length=length)

        if current_mode == self.MODE_DEMO and confidence >= fallback_threshold:
            return self.sequence_for_mode(self.MODES[0], length=length)

        return [self.MATCH_NONE] * length

    def _recognition_confidence(self) -> float:
        if self.last_match_mode in self.AUTH_TOKENS:
            if self.experimental_object_model_enabled:
                result = self.latest_gate_results.get(self.last_match_mode)
                if result is not None and result.quality_score is not None:
                    score = float(result.quality_score)
                    if score < 0.0:
                        return 0.0
                    if score > 1.0:
                        return 1.0
                    return score
            return 1.0
        return 0.0

    def capture_scene(self) -> tuple[bool, str]:
        """Record the empty scene, with the object out of frame.

        Binding an object needs to know what the view looks like without it.
        ORB has no notion of objects; it describes whatever texture is in the
        frame, so a reference captured straight from a tripod is mostly the wall
        behind the object and matches that wall with the object taken away.
        Measured before this existed: 414 reference keypoints, 189 inliers with
        the object absent, and a *different* object matching just as well - the
        cue was not discriminating anything.

        Held in memory only, and consumed by the next :meth:`capture_reference`,
        so a stale scene cannot quietly authorise a later binding.
        """
        with self.lock:
            frame = None if self.latest_frame is None else self.latest_frame.copy()
        if frame is None:
            return False, text.AI_GATE_NO_FRAME

        with self.lock:
            self.scene_frame = frame
        return True, text.AI_GATE_SCENE_CAPTURED

    @property
    def scene_captured(self) -> bool:
        with self.lock:
            return self.scene_frame is not None

    def discard_scene(self) -> None:
        with self.lock:
            self.scene_frame = None

    def capture_reference(self, mode: str) -> tuple[bool, str]:
        self._validate_mode(mode)
        if self.latest_frame is None:
            return False, text.AI_GATE_NO_FRAME

        with self.lock:
            scene_frame = None if self.scene_frame is None else self.scene_frame.copy()
        if scene_frame is None:
            return False, text.AI_GATE_SCENE_NOT_CAPTURED

        with self.lock:
            frame = None if self.latest_frame is None else self.latest_frame.copy()
        if frame is None:
            return False, text.AI_GATE_NO_FRAME

        # Raw grayscale for asking what changed, equalised grayscale for asking
        # what ORB would match. Using the equalised image for the difference
        # remaps the background along with the object and reports a third of the
        # view as changed for an object covering an eighth of it.
        scene_diff_gray = self.matcher.to_diff_gray(scene_frame)
        mask = self.matcher.object_mask(
            scene_diff_gray, self.matcher.to_diff_gray(frame)
        )
        if mask is None:
            # Either nothing changed enough to be an object, or the change is
            # spread across the view rather than concentrated in one thing held
            # up - the camera or the lighting moved. Both are the operator's to
            # fix, and both are reported rather than silently bound.
            return False, self._why_no_object(scene_diff_gray, frame)

        candidate_state = self._best_object_reference_state(scene_frame)
        if candidate_state is None:
            return False, text.AI_GATE_OBJECT_NOT_DISTINCT

        # The negative test. Restricting where the template comes from is the
        # fix; proving it no longer answers to the empty scene is what stops the
        # same defect shipping again unnoticed.
        scene_match_gray = self.matcher.to_gray(scene_frame)
        if self.matcher.explains_frame(candidate_state, scene_match_gray):
            return False, text.AI_GATE_OBJECT_IS_THE_SCENE

        committed = self._commit_reference(mode, candidate_state)
        if committed[0]:
            self.discard_scene()
        return committed

    def _why_no_object(self, scene_diff_gray: Any, frame: Any) -> str:
        """Which of the two capture failures to show the operator.

        Worth telling apart: "hold it closer" and "stop moving the camera" ask
        for opposite things, and an operator given the wrong one will keep
        making the capture worse.
        """
        try:
            covered, dominance = self.matcher.change_profile(
                scene_diff_gray, self.matcher.to_diff_gray(frame)
            )
        except cv2.error:
            return text.AI_GATE_OBJECT_NOT_DISTINCT
        if covered > self.matcher.max_object_area_ratio:
            return text.AI_GATE_SCENE_CHANGED
        if covered > 0.0 and dominance < self.matcher.min_object_dominance:
            return text.AI_GATE_SCENE_CHANGED
        return text.AI_GATE_OBJECT_NOT_DISTINCT

    def register_reference_from_image_bytes(
        self, mode: str, payload: bytes
    ) -> tuple[bool, str]:
        """Register an object-cue reference from an encoded image file payload.

        The image is decoded locally and never persisted; only the derived
        feature template is stored, matching the camera-capture path.
        """
        self._validate_mode(mode)
        image = self._decode_reference_image(payload)
        if image is None:
            return False, text.AI_GATE_IMAGE_UNREADABLE

        candidate_state = self._reference_state_from_image(
            self._scale_reference_image(image)
        )
        if candidate_state is None:
            return False, text.AI_GATE_IMAGE_TOO_SIMPLE

        return self._commit_reference(mode, candidate_state)

    def _decode_reference_image(self, payload: bytes) -> Any | None:
        if not payload:
            return None
        try:
            buffer = np.frombuffer(payload, dtype=np.uint8)
            image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
        except (cv2.error, ValueError) as exc:
            LOG.debug("reference image decode failed: %s", exc)
            return None
        if image is None or image.size == 0:
            return None
        return image

    def _scale_reference_image(self, image: Any) -> Any:
        """Downscale large images toward the camera frame scale.

        References registered from files must live at a scale comparable to
        the live camera frames they are later matched against; keypoints from
        a full-resolution photo would not correspond to the 320x240 stream.
        """
        height, width = image.shape[:2]
        if height <= 0 or width <= 0:
            return image
        frame_width, frame_height = self.FRAME_SIZE
        scale = min(frame_width / width, frame_height / height)
        if scale >= 1.0:
            return image
        new_size = (max(1, round(width * scale)), max(1, round(height * scale)))
        return cv2.resize(image, new_size, interpolation=cv2.INTER_AREA)

    def _commit_reference(
        self, mode: str, candidate_state: dict[str, Any]
    ) -> tuple[bool, str]:
        if self._references_too_similar(mode, candidate_state):
            return (
                False,
                text.AI_GATE_CUES_TOO_SIMILAR,
            )

        try:
            updated_references = dict(self.reference_data)
            updated_references[mode] = candidate_state
            self.store.save(updated_references)
        except OSError as exc:
            LOG.debug("object cue reference save failed: %s", exc)
            return False, text.AI_GATE_SAVE_FAILED

        candidate_state["path"] = self.state_blob_path
        with self.lock:
            self.reference_data[mode] = candidate_state
            self.last_match_mode = self.MATCH_NONE
            self.object_detected = False
            self.match_states = {ref_mode: False for ref_mode in self.MODES}
            self.match_history = []

        return True, text.AI_GATE_OBJECT_MATCHED

    def _best_object_reference_state(self, scene_frame: Any) -> dict[str, Any] | None:
        """Best masked candidate across several frames.

        Sampling more than one frame is what makes capture survive motion blur
        and a refocus on real hardware; the previous whole-frame version did the
        same and the robustness is worth keeping. What changed is that each
        candidate is now built only from the region that differs from
        *scene_frame*, so none of them describe the background.
        """
        candidates = []
        for _ in range(self.REFERENCE_CAPTURE_SAMPLES):
            with self.lock:
                frame = None if self.latest_frame is None else self.latest_frame.copy()
            state = self.matcher.object_reference_state(scene_frame, frame)
            if state is not None:
                candidates.append(state)
            time.sleep(0.12)

        if not candidates:
            return None
        best = max(candidates, key=lambda state: len(state["kp"]))
        return cast(dict[str, Any], best)

    def get_status(self) -> dict[str, Any]:
        camera_status = self.camera.status()
        status = {
            "camera_ready": bool(camera_status["ready"]),
            "object_detected": self.object_detected,
            "matched_mode": self.last_match_mode,
            "match_states": dict(self.match_states),
            "registered_modes": {
                mode: self.reference_data[mode]["des"] is not None
                for mode in self.MODES
            },
            "camera_backend": camera_status["backend"],
            "last_camera_error": camera_status["last_error"],
            "camera_backend_warnings": camera_status.get("backend_warnings", []),
            "stream_resolution": camera_status["resolution"],
            "fps_target": camera_status["fps_target"],
            "last_frame_at": camera_status.get("last_frame_at"),
            "frames_yielded": camera_status.get("frames_yielded", 0),
        }
        if self.experimental_object_model_enabled:
            status["object_gate"] = {
                mode: {
                    "state": result.state,
                    "stable_frames": result.stable_frames,
                    "reason_code": result.reason_code,
                }
                for mode, result in self.latest_gate_results.items()
            }
        if recognition_mode() == self.MODE_DEMO and debug_enabled():
            status["recognition_debug"] = {
                "mode": recognition_mode(),
                "confidence": self._recognition_confidence(),
                "true_unlock_threshold": true_unlock_threshold(),
                "dummy_fallback_threshold": dummy_fallback_threshold(),
            }
        return status

    def clear_references(self) -> tuple[bool, str]:
        empty = {mode: self._empty_reference() for mode in self.MODES}
        try:
            self.store.save(empty)
        except OSError as exc:
            LOG.debug("object cue reference clear failed: %s", exc)
            return False, text.AI_GATE_CLEAR_FAILED

        with self.lock:
            self.reference_data = empty
            self.last_match_mode = self.MATCH_NONE
            self.object_detected = False
            self.match_states = {mode: False for mode in self.MODES}
            self.match_history = []
            self.latest_gate_results = {}

        return True, text.AI_GATE_CUES_CLEARED

    def _cue_scores(self, reference_data: dict, frame_gray: Any) -> list:
        """Live scores for the preview, when the bench flag asks for them.

        Costs a second feature extraction per frame, so it is not computed
        unless something is going to display it.
        """
        if not cue_debug_overlay_enabled():
            return []
        kp, des = self.matcher.orb.detectAndCompute(frame_gray, None)
        scored = []
        for index, state in enumerate(reference_data.values()):
            score = self.matcher.score_descriptors(state, kp, des)
            if score is not None:
                scored.append((f"entry {index + 1}", score))
        return scored

    def _draw_cue_scores(self, image: Any, scores: list) -> None:
        """Write the scores under the preview, against the bar each has to clear.

        Numbered by position rather than named, matching how the Store page
        already refers to entries, and so the overlay says nothing the page
        does not already say about how many there are.
        """
        if not scores:
            return
        h, w, _ = image.shape
        line_height = 14
        top = h - 4 - line_height * len(scores)
        cv2.rectangle(image, (0, top - 4), (w, h), (0, 0, 0), -1)
        for index, (label, score) in enumerate(scores):
            clears = (
                score["good_matches"] > score["required_good_matches"]
                and score["inliers"] > score["required_inliers"]
            )
            cv2.putText(
                image,
                f"{label}  tpl {score['keypoints']}  frame {score['frame_keypoints']}"
                f"  good {score['good_matches']}/{score['required_good_matches']}"
                f"  inliers {score['inliers']}/{score['required_inliers']}",
                (8, top + line_height * (index + 1) - 3),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.38,
                (0, 255, 0) if clears else (0, 165, 255),
                1,
            )

    def _draw_match_status(self, image: Any) -> None:
        h, w, _ = image.shape
        cv2.rectangle(image, (0, 0), (w, 50), (0, 0, 0), -1)
        cv2.putText(
            image,
            text.AI_GATE_ACTIVE,
            (20, 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 165, 255),
            2,
        )

        if self.last_match_mode in self.AUTH_TOKENS:
            cv2.circle(image, (w - 15, 15), 8, (0, 255, 0), -1)
            cv2.putText(
                image,
                text.AI_GATE_MATCH,
                (w - 80, 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2,
            )
            cv2.rectangle(image, (5, 55), (w - 5, h - 5), (0, 255, 0), 3)
            cv2.putText(
                image,
                text.AI_GATE_OBJECT_MATCHED,
                (15, 75),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2,
            )
            cv2.putText(
                image,
                text.AI_GATE_OBJECT_DETECTED,
                (15, 100),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                1,
            )
            return

        if self.last_match_mode == self.MATCH_AMBIGUOUS:
            cv2.circle(image, (w - 15, 15), 8, (0, 165, 255), -1)
            cv2.putText(
                image,
                text.AI_GATE_AMBIGUOUS,
                (w - 85, 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 165, 255),
                2,
            )
            cv2.rectangle(image, (5, 55), (w - 5, h - 5), (0, 165, 255), 3)
            cv2.putText(
                image,
                text.AI_GATE_AMBIGUOUS_CUE,
                (15, 75),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 165, 255),
                2,
            )
            cv2.putText(
                image,
                text.AI_GATE_CUES_TOO_SIMILAR,
                (15, 100),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 165, 255),
                1,
            )
            return

        cv2.putText(
            image,
            text.AI_GATE_NO_MATCH,
            (15, 75),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (100, 100, 255),
            2,
        )
        cv2.putText(
            image,
            text.AI_GATE_PRESENT_OBJECT,
            (15, 100),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (100, 100, 255),
            1,
        )

    def generate_frames(self) -> Iterator[bytes]:
        # The background matcher thread and a WebUI /video_feed request both
        # call this method, on the same shared camera, at the same time. The
        # bug this guards against: closing the camera whenever *either* one's
        # generator exits, which used to happen unconditionally in the
        # `finally` below. A browser tab navigating away from the Store page
        # would tear down the camera the TUI's own matcher thread was still
        # reading from; the next read then silently failed to produce a
        # frame, `_update_match_result` was never called again, and
        # `last_match_mode` stayed frozen at whatever it last was - "matched"
        # if that happened to be the state right after registering an object
        # cue. Recover then kept succeeding with no object in view, for the
        # rest of the process's life, because nothing was actually checking
        # the camera any more. Counting active generator instances and only
        # releasing the hardware when the last one exits keeps the
        # long-lived background consumer's camera alive across a WebUI
        # viewer connecting and disconnecting.
        with self.lock:
            self._camera_consumers += 1
        frame_delay = 1.0 / self.TARGET_FPS
        empty_reads = 0
        try:
            while not self._stop_event.is_set():
                loop_start = time.time()
                success, frame = self.camera.read()
                if not success:
                    empty_reads += 1
                    if empty_reads == 1 or empty_reads % 10 == 0:
                        LOG.warning(
                            "Camera frame unavailable (backend=%s): %s",
                            self.camera.status()["backend"],
                            self.camera.status()["last_error"],
                        )
                    placeholder = self._camera_error_frame()
                    ok, buffer = cv2.imencode(
                        ".jpg",
                        placeholder,
                        [cv2.IMWRITE_JPEG_QUALITY, 55],
                    )
                    if ok:
                        yield (
                            b"--frame\r\n"
                            b"Content-Type: image/jpeg\r\n\r\n"
                            + buffer.tobytes()
                            + b"\r\n"
                        )
                        self.camera.mark_frame_yielded()
                    time.sleep(frame_delay)
                    continue
                empty_reads = 0

                with self.lock:
                    self.latest_frame = frame.copy()
                    reference_data = {
                        mode: dict(state) for mode, state in self.reference_data.items()
                    }

                image = self._prepare_stream_frame(frame)

                processed_gray = self._to_gray(frame)
                matches = {
                    mode: self._match_reference_state(state, processed_gray)
                    for mode, state in reference_data.items()
                }
                cue_scores = self._cue_scores(reference_data, processed_gray)
                if self.experimental_object_model_enabled:
                    gate_results = {
                        mode: self.object_gate.evaluate_frame(
                            frame=frame, orb_match=match
                        )
                        for mode, match in matches.items()
                    }
                    self._update_match_result_from_gate_results(gate_results)
                else:
                    self._update_match_result(matches)
                self._draw_match_status(image)
                self._draw_cue_scores(image, cue_scores)

                ok, buffer = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 55])
                if not ok:
                    LOG.error("JPEG encode failed for camera frame")
                    continue

                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n"
                )
                self.camera.mark_frame_yielded()

                elapsed = time.time() - loop_start
                if elapsed < frame_delay:
                    time.sleep(frame_delay - elapsed)
        finally:
            self._finish_camera_consumer()

    def _finish_camera_consumer(self) -> None:
        """Release the shared camera only once every generate_frames() caller is gone."""
        with self.lock:
            self._camera_consumers = max(0, self._camera_consumers - 1)
            last_consumer = self._camera_consumers == 0
        if last_consumer:
            self.camera.close()

    def _camera_error_frame(self) -> Any:
        width, height = self.FRAME_SIZE
        image = np.zeros((height, width, 3), dtype=np.uint8)
        cv2.putText(
            image,
            "Camera unavailable",
            (12, int(height * 0.45)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 180, 255),
            2,
        )
        cv2.putText(
            image,
            "Check camera backend",
            (12, int(height * 0.62)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (180, 180, 180),
            1,
        )
        return image

    def _prepare_stream_frame(self, frame: Any) -> Any:
        # Apply a single deterministic horizontal mirror correction.
        return cv2.flip(frame, 1)

    def close(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join()
            self._thread = None
        # Unconditional: a full shutdown releases the hardware regardless of
        # whether some other generate_frames() caller still thinks it holds
        # it. Joining the background thread first means its own generator
        # has already run its finally and decremented; any remaining count
        # belongs to callers this process is shutting down anyway.
        self.release_camera()

    def release_camera(self) -> None:
        with self.lock:
            self._camera_consumers = 0
        self.camera.close()

    @property
    def matching_active(self) -> bool:
        return self._thread is not None

    def start(self) -> None:
        if self._thread is None:
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._generate_loop, daemon=True)
            self._thread.start()

    def _generate_loop(self) -> None:
        for _ in self.generate_frames():
            pass


def get_gesture_sequence(length: int = 1) -> list[str]:
    return gate.get_auth_sequence(length=length)


gate = AIGate()
