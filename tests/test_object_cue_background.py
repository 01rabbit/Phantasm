"""The object cue must gate on the object, not on the scene behind it.

`reference_state_from_image` ran ORB over the whole frame with no mask, so a
reference captured from a camera on a tripod was mostly the wall behind the
object. Matching that template against the same wall with the object taken away
still found inliers, so the demo's central claim - present the object or it
refuses - did not hold on real hardware: it opened with the object hidden.

Measured on the fixed scene these tests build: 414 reference keypoints, 189
inliers with the object absent, and a *different* object matching at 184. The
cue was not discriminating between objects at all; it was reading the room.
"""

from __future__ import annotations

import os
import sys
import unittest

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))

from phasmid.object_cue_matcher import ObjectCueMatcher


def _fixed_scene(seed: int = 3) -> np.ndarray:
    """A textured, structured view - what a tripod actually points at.

    Deliberately not random noise: noise is a pathological case for ORB and
    would let a weaker fix look like it worked.
    """
    image = np.full((240, 320, 3), 60, np.uint8)
    rng = np.random.default_rng(seed)
    for _ in range(40):
        x, y = int(rng.integers(0, 300)), int(rng.integers(0, 220))
        w, h = int(rng.integers(10, 50)), int(rng.integers(10, 40))
        colour = tuple(int(v) for v in rng.integers(40, 200, 3))
        cv2.rectangle(image, (x, y), (x + w, y + h), colour, -1)
    for i in range(0, 320, 17):
        cv2.line(image, (i, 0), (i, 239), (90, 90, 90), 1)
    cv2.putText(
        image, "SHELF", (20, 220), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2
    )
    return image


def _with_light_object(scene: np.ndarray) -> np.ndarray:
    image = scene.copy()
    cv2.rectangle(image, (120, 80), (200, 160), (250, 250, 250), -1)
    cv2.circle(image, (160, 120), 25, (20, 20, 20), -1)
    cv2.putText(
        image, "MUG", (126, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (10, 10, 10), 2
    )
    return image


def _with_dark_object(scene: np.ndarray) -> np.ndarray:
    image = scene.copy()
    cv2.rectangle(image, (120, 80), (200, 160), (30, 30, 30), -1)
    for i in range(6):
        cv2.line(image, (124, 84 + i * 12), (196, 84 + i * 12), (240, 240, 240), 2)
    cv2.putText(
        image, "KEY", (128, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (250, 250, 250), 2
    )
    return image


def _matcher() -> ObjectCueMatcher:
    return ObjectCueMatcher(
        min_reference_keypoints=10,
        min_frame_descriptors=10,
        min_good_matches=10,
        min_inliers=8,
    )


class ObjectCueBackgroundTests(unittest.TestCase):
    def setUp(self):
        self.matcher = _matcher()
        self.scene = _fixed_scene()
        self.object_frame = _with_light_object(self.scene)
        self.other_object_frame = _with_dark_object(self.scene)
        self.reference = self.matcher.object_reference_state(
            self.scene, self.object_frame
        )
        self.assertIsNotNone(self.reference, "the object should be bindable")

    def _matches(self, frame) -> bool:
        return self.matcher.explains_frame(self.reference, self.matcher.to_gray(frame))

    def test_the_empty_scene_does_not_open_the_cue(self):
        """The defect, stated as a test. This is the demo's central claim."""
        self.assertFalse(
            self._matches(self.scene),
            "the scene alone matched the cue - the background is the key again",
        )

    def test_the_bound_object_still_opens_the_cue(self):
        """A fix that refuses everything would pass the test above for free."""
        self.assertTrue(self._matches(self.object_frame))

    def test_a_different_object_in_the_same_place_does_not_open_the_cue(self):
        """The old whole-frame template matched this too, at 184 inliers."""
        self.assertFalse(self._matches(self.other_object_frame))

    def test_the_whole_frame_template_is_what_matched_the_scene(self):
        """Pins the diagnosis, so a regression is recognisable rather than new.

        Kept as a characterisation of the old path: `reference_state_from_image`
        still exists for references registered from an image file, where there
        is no scene frame to subtract. This asserts *why* it was wrong when fed
        a tripod frame, which is the thing the mask fixes.
        """
        whole_frame = self.matcher.reference_state_from_image(self.object_frame)
        self.assertIsNotNone(whole_frame)
        self.assertTrue(
            self.matcher.explains_frame(whole_frame, self.matcher.to_gray(self.scene)),
            "if this stops matching, the diagnosis in this file needs revisiting",
        )
        self.assertGreater(len(whole_frame["kp"]), len(self.reference["kp"]))


class ObjectMaskTests(unittest.TestCase):
    def setUp(self):
        self.matcher = _matcher()
        self.scene = _fixed_scene()

    def _mask(self, frame):
        return self.matcher.object_mask(
            self.matcher.to_gray(self.scene), self.matcher.to_gray(frame)
        )

    def test_the_mask_covers_the_object_and_not_the_frame(self):
        mask = self._mask(_with_light_object(self.scene))
        self.assertIsNotNone(mask)
        covered = np.count_nonzero(mask) / float(mask.shape[0] * mask.shape[1])
        self.assertGreater(covered, 0.01)
        self.assertLess(covered, 0.30, "the mask spread beyond the object")

    def test_an_unchanged_view_yields_no_object(self):
        """Pressing capture without holding anything up must not bind."""
        self.assertIsNone(self._mask(self.scene))

    def test_a_view_that_changed_everywhere_is_refused(self):
        """The camera moved, or the lights did - the diff no longer isolates."""
        self.assertIsNone(self._mask(_fixed_scene(seed=99)))

    def test_a_mismatched_frame_size_is_refused_rather_than_raising(self):
        small = cv2.resize(self.scene, (160, 120))
        self.assertIsNone(
            self.matcher.object_mask(
                self.matcher.to_gray(self.scene), self.matcher.to_gray(small)
            )
        )

    def test_object_reference_state_refuses_without_a_scene(self):
        self.assertIsNone(
            self.matcher.object_reference_state(None, _with_light_object(self.scene))
        )
        self.assertIsNone(self.matcher.object_reference_state(self.scene, None))
