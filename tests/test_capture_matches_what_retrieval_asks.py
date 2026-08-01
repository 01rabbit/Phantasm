"""Capture is held to the bar retrieval will apply, not an easier one.

Reported from the device as a suspicion, and it was correct: the two paths were
never symmetric, and the asymmetry ran the wrong way.

Capture *builds* a template from the frame in front of it, so it succeeds by
construction. The only test it ran was the negative one — that the template
does not answer to the empty scene (#184). Nothing asked whether it would still
answer to the *object* a moment later.

Retrieval then asks for something strictly harder. Past the per-frame
thresholds, `_update_match_result` requires the entry to appear in
`MATCH_HISTORY_REQUIRED` of the last `MATCH_HISTORY_FRAMES` frames — at
`TARGET_FPS`, about a second of consistent matching. A template scoring near
the bar flickers across that window and never accumulates.

The result an operator sees: a clean capture, a green toast, and an entry that
will not open — with nothing said in between, and the two events far enough
apart that they do not look related.

So capture now samples fresh frames of the object still being held and applies
the same count. Failing here costs a re-capture. Failing the old way costs
finding out at the moment the data is needed.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))

from phasmid.ai_gate import AIGate

HEIGHT, WIDTH = 240, 320


def wall(level: int = 128) -> np.ndarray:
    return np.full((HEIGHT, WIDTH, 3), level, np.uint8)


def an_object() -> np.ndarray:
    return np.random.default_rng(4).integers(35, 90, (90, 110, 3)).astype(np.uint8)


def held_up(background: np.ndarray) -> np.ndarray:
    scene = background.copy()
    obj = an_object()
    scene[70 : 70 + obj.shape[0], 100 : 100 + obj.shape[1]] = obj
    return scene


class ScriptedGate(AIGate):
    """An AIGate whose live frames are scripted rather than photographed.

    `latest_frame` is a plain attribute on the real class, so there is nothing
    to patch that survives the read loop; a property with a setter that drops
    what `__init__` assigns is the least invasive way in. The last frame
    repeats once the script runs out, which is what a still camera does.
    """

    def __init__(self, frames):
        self._supply = list(frames)
        super().__init__()

    @property
    def latest_frame(self):
        return self._supply.pop(0) if len(self._supply) > 1 else self._supply[0]

    @latest_frame.setter
    def latest_frame(self, _value):
        pass


class CaptureAppliesTheRetrievalBarTests(unittest.TestCase):
    def setUp(self):
        # A fresh state directory per test: the gate loads whatever templates
        # it finds at construction, so a previous test's successful capture
        # would otherwise be sitting there pretending to be this one's.
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._dirs = mock.patch.dict(
            os.environ,
            {
                "PHASMID_CONFIG_DIR": os.path.join(self._tmp.name, "config"),
                "PHASMID_STATE_DIR": os.path.join(self._tmp.name, "state"),
            },
        )
        self._dirs.start()
        self.addCleanup(self._dirs.stop)
        self._nap = mock.patch("time.sleep", lambda _s: None)
        self._nap.start()
        self.addCleanup(self._nap.stop)
        self.gate = None

    def _capture_with(self, scene, live_frames):
        self.gate = ScriptedGate(live_frames)
        self.gate.camera = mock.MagicMock()
        self.gate.scene_frame = scene
        return self.gate.capture_reference(self.gate.MODES[0])

    def test_an_object_that_keeps_matching_is_bound(self):
        scene = wall()
        present = held_up(scene)
        ok, message = self._capture_with(scene, [present] * 30)
        self.assertTrue(ok, message)

    def test_an_object_that_stops_matching_is_refused_at_capture(self):
        """The reported failure, moved to where it can be acted on.

        The object is there for the frames the template is cut from and gone
        for the frames that follow — the shape of a cue that binds cleanly and
        then does not open anything.
        """
        scene = wall()
        present = held_up(scene)
        # Present while the template is cut, gone for the frames after it.
        frames = [present] * 12 + [wall()] * 20
        ok, message = self._capture_with(scene, frames)
        self.assertFalse(ok, "an unrepeatable template was bound anyway")
        self.assertIn("did not keep matching", message)

    def test_the_refusal_names_what_to_change(self):
        """A refusal an operator cannot act on is only half a refusal."""
        scene = wall()
        frames = [held_up(scene)] * 12 + [wall()] * 20
        _ok, message = self._capture_with(scene, frames)
        for hint in ("closer", "light", "detail"):
            self.assertIn(hint, message)

    def test_it_asks_for_the_same_count_retrieval_asks_for(self):
        """If these drift apart, capture starts lying again."""
        self.assertEqual(AIGate.MATCH_HISTORY_REQUIRED, 3)
        self.assertEqual(AIGate.MATCH_HISTORY_FRAMES, 5)

    def test_nothing_is_bound_when_the_check_fails(self):
        scene = wall()
        frames = [held_up(scene)] * 12 + [wall()] * 20
        self._capture_with(scene, frames)
        self.assertIsNone(self.gate.reference_data[self.gate.MODES[0]]["des"])

    def test_the_empty_scene_is_kept_so_the_operator_can_retry(self):
        """A refused capture should not force the scene shot to be redone."""
        scene = wall()
        frames = [held_up(scene)] * 12 + [wall()] * 20
        self._capture_with(scene, frames)
        self.assertIsNotNone(self.gate.scene_frame)


if __name__ == "__main__":
    unittest.main()
