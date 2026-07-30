"""A bound object has to survive being presented a second time.

`min_good_matches=50` / `min_inliers=30` were calibrated when a reference
template covered the whole frame and carried 400-900 keypoints. Masking the
template to the object leaves 72 on a plain wall, and the same absolute counts
then demand that most of the template be re-found almost exactly. Measured
before this module existed, on a 72-keypoint template:

    identical frame          good=62  inliers=62   (floor is 50)
    +-6 grayscale noise      good=42  inliers=41   REFUSED
    5px shift + noise        good=32  inliers=32   REFUSED
    10% closer + noise       good=35  inliers=34   REFUSED

One of six presentations matched, and the noise that broke it is less than a
real sensor produces. Reported from the device as "recognition at /retrieve is
too strict".

The thresholds are now a proportion of the template, floored and capped by the
absolute counts. That is safe because discrimination never came from the counts
being high - it comes from the template describing the object and nothing else.
On the same scene the empty view and a different object each score **zero**
good matches, so the separation is 42-vs-0, not 42-vs-49. These tests hold both
ends: presentations must match, and non-objects must not.
"""

from __future__ import annotations

import os
import sys
import unittest

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.dirname(__file__))

from test_object_cue_background import (
    _fixed_scene,
    _held_up,
    _plain_room,
    _with_dark_object,
    _with_light_object,
)

from phasmid.ai_gate import AIGate
from phasmid.object_cue_matcher import ObjectCueMatcher


def _present_again(
    image: np.ndarray,
    *,
    dx: int = 0,
    dy: int = 0,
    noise: int = 0,
    scale: float = 1.0,
    rotation: float = 0.0,
) -> np.ndarray:
    """The same object held up again - never the same pixels twice."""
    height, width = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((width / 2, height / 2), rotation, scale)
    matrix[0, 2] += dx
    matrix[1, 2] += dy
    out = cv2.warpAffine(
        image, matrix, (width, height), borderMode=cv2.BORDER_REPLICATE
    )
    if noise:
        rng = np.random.default_rng(7)
        grain = rng.integers(-noise, noise + 1, out.shape, dtype=np.int16)
        out = np.clip(out.astype(np.int16) + grain, 0, 255).astype(np.uint8)
    return out


def _production_matcher() -> ObjectCueMatcher:
    """The gate's own numbers, not the permissive ones the other module uses."""
    return ObjectCueMatcher(
        min_reference_keypoints=AIGate.MIN_REFERENCE_KEYPOINTS,
        min_frame_descriptors=AIGate.MIN_FRAME_DESCRIPTORS,
        min_good_matches=AIGate.MIN_GOOD_MATCHES,
        min_inliers=AIGate.MIN_INLIERS,
    )


PRESENTATIONS = (
    ("held still", {}),
    ("sensor noise", {"noise": 6}),
    ("shifted slightly", {"dx": 5, "dy": 3, "noise": 6}),
    ("shifted and tilted", {"dx": 10, "dy": 6, "rotation": 5, "noise": 6}),
    ("held closer", {"scale": 1.1, "noise": 6}),
)


class PlainWallPresentationTests(unittest.TestCase):
    """A camera on a desk pointed at a wall - where this failed on hardware."""

    def setUp(self):
        self.matcher = _production_matcher()
        self.room = _plain_room()
        self.object_frame = _held_up(self.room)
        self.reference = self.matcher.object_reference_state(
            self.room, self.object_frame
        )
        self.assertIsNotNone(self.reference, "the object should be bindable")

    def _matches(self, frame) -> bool:
        return self.matcher.explains_frame(self.reference, self.matcher.to_gray(frame))

    def test_the_template_is_small_which_is_the_whole_problem(self):
        """States the premise, so the tests below read as consequences."""
        self.assertLess(
            len(self.reference["kp"]),
            AIGate.MIN_GOOD_MATCHES * 2,
            "if masked templates got large, revisit the ratios",
        )

    def test_every_presentation_of_the_bound_object_matches(self):
        for name, how in PRESENTATIONS:
            with self.subTest(presentation=name):
                self.assertTrue(
                    self._matches(_present_again(self.object_frame, **how)),
                    f"the bound object was refused when {name}",
                )

    def test_the_empty_wall_still_does_not_match(self):
        for name, how in (("still", {}), ("with noise", {"noise": 6})):
            with self.subTest(presentation=name):
                self.assertFalse(self._matches(_present_again(self.room, **how)))

    def test_a_different_object_still_does_not_match(self):
        other = _with_dark_object(self.room)
        for name, how in (("still", {}), ("with noise", {"noise": 6})):
            with self.subTest(presentation=name):
                self.assertFalse(self._matches(_present_again(other, **how)))


class TexturedScenePresentationTests(unittest.TestCase):
    """The larger template, where the absolute counts were always reachable."""

    def setUp(self):
        self.matcher = _production_matcher()
        self.scene = _fixed_scene()
        self.object_frame = _with_light_object(self.scene)
        self.reference = self.matcher.object_reference_state(
            self.scene, self.object_frame
        )
        self.assertIsNotNone(self.reference)

    def _matches(self, frame) -> bool:
        return self.matcher.explains_frame(self.reference, self.matcher.to_gray(frame))

    def test_every_presentation_of_the_bound_object_matches(self):
        for name, how in PRESENTATIONS:
            with self.subTest(presentation=name):
                self.assertTrue(self._matches(_present_again(self.object_frame, **how)))

    def test_the_scene_and_a_different_object_still_do_not_match(self):
        for name, frame in (
            ("empty scene", self.scene),
            ("different object", _with_dark_object(self.scene)),
        ):
            with self.subTest(frame=name):
                self.assertFalse(self._matches(_present_again(frame, noise=6)))


class EffectiveThresholdTests(unittest.TestCase):
    def setUp(self):
        self.matcher = _production_matcher()

    def _for(self, keypoints: int) -> tuple[int, int]:
        return self.matcher.effective_thresholds({"kp": [object()] * keypoints})

    def test_a_large_template_is_never_asked_for_more_than_before(self):
        """The absolute counts are a ceiling: this can only relax, never tighten."""
        good, inliers = self._for(1000)
        self.assertEqual(good, AIGate.MIN_GOOD_MATCHES)
        self.assertEqual(inliers, AIGate.MIN_INLIERS)

    def test_a_masked_template_is_asked_for_a_share_of_itself(self):
        good, inliers = self._for(72)
        self.assertEqual(good, 18)
        self.assertEqual(inliers, 11)

    def test_a_tiny_template_still_has_to_agree_on_something(self):
        """A proportion of almost nothing is nothing - the floors stop that."""
        good, inliers = self._for(4)
        self.assertEqual(good, ObjectCueMatcher.GOOD_MATCH_FLOOR)
        self.assertEqual(inliers, ObjectCueMatcher.INLIER_FLOOR)

    def test_an_empty_reference_does_not_raise(self):
        self.assertEqual(
            self.matcher.effective_thresholds({"kp": None}),
            (ObjectCueMatcher.GOOD_MATCH_FLOOR, ObjectCueMatcher.INLIER_FLOOR),
        )
        self.assertEqual(
            self.matcher.effective_thresholds(None),
            (ObjectCueMatcher.GOOD_MATCH_FLOOR, ObjectCueMatcher.INLIER_FLOOR),
        )

    def test_the_ratios_can_be_tuned_for_the_camera_in_front_of_the_device(self):
        strict = ObjectCueMatcher(
            min_reference_keypoints=60,
            min_frame_descriptors=10,
            min_good_matches=50,
            min_inliers=30,
            min_good_match_ratio=1.0,
            min_inlier_ratio=1.0,
        )
        self.assertEqual(strict.effective_thresholds({"kp": [object()] * 72}), (50, 30))


if __name__ == "__main__":
    unittest.main()
