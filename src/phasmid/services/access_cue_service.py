from __future__ import annotations

from ..ai_gate import gate
from ..config import recognition_mode


class AccessCueService:
    """Boundary service for object-cue camera and match orchestration."""

    def __init__(self):
        self.gate = gate

    def modes(self):
        return self.gate.MODES

    def auth_tokens(self):
        return self.gate.AUTH_TOKENS

    def match_none(self):
        return self.gate.MATCH_NONE

    def match_ambiguous(self):
        return self.gate.MATCH_AMBIGUOUS

    def current_match_mode(self):
        return self.gate.last_match_mode

    def latest_frame_copy(self):
        with self.gate.lock:
            return (
                None
                if self.gate.latest_frame is None
                else self.gate.latest_frame.copy()
            )

    def camera_ready(self):
        return bool(self.gate.get_status().get("camera_ready"))

    def status(self):
        return self.gate.get_status()

    def auth_sequence(self, length=1):
        return self.gate.get_auth_sequence(length=length)

    def recognition_mode(self):
        return recognition_mode()

    def sequence_for_mode(self, mode, length=1):
        return self.gate.sequence_for_mode(mode, length=length)

    def capture_reference(self, mode):
        return self.gate.capture_reference(mode)

    def clear_references(self):
        return self.gate.clear_references()

    def start(self):
        return self.gate.start()

    def generate_frames(self):
        return self.gate.generate_frames()

    def close(self):
        self.gate.close()

    def release_camera(self):
        self.gate.release_camera()


access_cue_service = AccessCueService()
