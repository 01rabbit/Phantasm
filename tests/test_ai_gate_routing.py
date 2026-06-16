import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))

from phasmid.ai_gate import AIGate


class TestAIGateRecognitionRouting(unittest.TestCase):
    def setUp(self):
        self._old_env = {
            name: os.environ.get(name)
            for name in (
                "PHASMID_RECOGNITION_MODE",
                "PHASMID_TRUE_UNLOCK_THRESHOLD",
                "PHASMID_DUMMY_FALLBACK_THRESHOLD",
            )
        }
        for name in self._old_env:
            os.environ.pop(name, None)

    def tearDown(self):
        for name, value in self._old_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    def _gate(self, tmp):
        gate = AIGate(reference_dir=tmp)
        self.addCleanup(gate.close)
        return gate

    def test_strict_mode_returns_no_match_without_stable_object(self):
        with tempfile.TemporaryDirectory() as tmp:
            gate = self._gate(tmp)
            gate.last_match_mode = gate.MATCH_NONE

            self.assertEqual(gate.get_auth_sequence(), [gate.MATCH_NONE])

    def test_strict_mode_returns_matched_token_when_confident(self):
        with tempfile.TemporaryDirectory() as tmp:
            gate = self._gate(tmp)
            gate.last_match_mode = "secret"

            self.assertEqual(gate.get_auth_sequence(), ["reference_secret_matched"])

    def test_coercion_safe_mode_routes_low_confidence_to_dummy_token(self):
        os.environ["PHASMID_RECOGNITION_MODE"] = "coercion_safe"

        with tempfile.TemporaryDirectory() as tmp:
            gate = self._gate(tmp)
            gate.last_match_mode = gate.MATCH_NONE

            self.assertEqual(gate.get_auth_sequence(), ["reference_dummy_matched"])
