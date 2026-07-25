import os
import sys
import tempfile
import unittest

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))

from phasmid import strings as text
from phasmid.ai_gate import AIGate


def _textured_image(width=320, height=240, seed=42):
    rng = np.random.default_rng(seed)
    return rng.integers(0, 256, size=(height, width, 3), dtype=np.uint8)


def _encode_png(image):
    ok, buffer = cv2.imencode(".png", image)
    if not ok:
        raise RuntimeError("failed to encode test image")
    return buffer.tobytes()


class TestAIGateImageFileRegistration(unittest.TestCase):
    def _gate(self, tmp):
        gate = AIGate(reference_dir=tmp)
        self.addCleanup(gate.close)
        return gate

    def test_register_from_image_bytes_binds_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            gate = self._gate(tmp)

            success, message = gate.register_reference_from_image_bytes(
                "dummy", _encode_png(_textured_image())
            )

            self.assertTrue(success, message)
            self.assertEqual(message, text.AI_GATE_OBJECT_MATCHED)
            self.assertTrue(gate.get_status()["registered_modes"]["dummy"])
            self.assertFalse(gate.get_status()["registered_modes"]["secret"])

    def test_register_from_image_bytes_persists_across_reload(self):
        with tempfile.TemporaryDirectory() as tmp:
            gate = self._gate(tmp)
            success, message = gate.register_reference_from_image_bytes(
                "secret", _encode_png(_textured_image(seed=7))
            )
            self.assertTrue(success, message)
            gate.close()

            reloaded = self._gate(tmp)
            self.assertTrue(reloaded.get_status()["registered_modes"]["secret"])

    def test_register_rejects_unreadable_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            gate = self._gate(tmp)

            success, message = gate.register_reference_from_image_bytes(
                "dummy", b"not-an-image"
            )

            self.assertFalse(success)
            self.assertEqual(message, text.AI_GATE_IMAGE_UNREADABLE)

    def test_register_rejects_empty_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            gate = self._gate(tmp)

            success, message = gate.register_reference_from_image_bytes("dummy", b"")

            self.assertFalse(success)
            self.assertEqual(message, text.AI_GATE_IMAGE_UNREADABLE)

    def test_register_rejects_featureless_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            gate = self._gate(tmp)
            flat = np.full((240, 320, 3), 128, dtype=np.uint8)

            success, message = gate.register_reference_from_image_bytes(
                "dummy", _encode_png(flat)
            )

            self.assertFalse(success)
            self.assertEqual(message, text.AI_GATE_IMAGE_TOO_SIMPLE)

    def test_register_rejects_cue_too_similar_to_other_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            gate = self._gate(tmp)
            payload = _encode_png(_textured_image(seed=11))

            success, message = gate.register_reference_from_image_bytes(
                "dummy", payload
            )
            self.assertTrue(success, message)

            success, message = gate.register_reference_from_image_bytes(
                "secret", payload
            )

            self.assertFalse(success)
            self.assertEqual(message, text.AI_GATE_CUES_TOO_SIMILAR)

    def test_register_rejects_unknown_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            gate = self._gate(tmp)

            with self.assertRaises(ValueError):
                gate.register_reference_from_image_bytes(
                    "unknown", _encode_png(_textured_image())
                )

    def test_large_image_is_downscaled_to_camera_frame_scale(self):
        with tempfile.TemporaryDirectory() as tmp:
            gate = self._gate(tmp)
            large = _textured_image(width=1280, height=960, seed=5)

            success, message = gate.register_reference_from_image_bytes(
                "dummy", _encode_png(large)
            )

            self.assertTrue(success, message)
            height, width = gate.reference_data["dummy"]["shape"]
            frame_width, frame_height = gate.FRAME_SIZE
            self.assertLessEqual(width, frame_width)
            self.assertLessEqual(height, frame_height)

    def test_small_image_is_not_upscaled(self):
        with tempfile.TemporaryDirectory() as tmp:
            gate = self._gate(tmp)
            small = _textured_image(width=160, height=120, seed=9)

            success, message = gate.register_reference_from_image_bytes(
                "dummy", _encode_png(small)
            )

            self.assertTrue(success, message)
            self.assertEqual(gate.reference_data["dummy"]["shape"], (120, 160))


if __name__ == "__main__":
    unittest.main()
