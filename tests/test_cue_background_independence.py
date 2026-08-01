"""The bound object opens the container. Not the room it was bound in.

Reported from the device: a Face registered in one place stopped matching once
the background changed, so the data could only be recovered in the environment
it was stored in. For a device whose whole premise is being carried and used
under pressure somewhere else, that is not a rough edge — it is the wrong
product.

The cause was `to_gray` applying `cv2.equalizeHist`, which is *global*: one
mapping derived from the whole frame's histogram. The two-shot capture (#184)
already restricted *where* descriptors come from, so the template contained
only object keypoints — but their values were still computed through a mapping
the background had a vote in. Change the wall and the same object's bytes
produce different descriptors.

These tests hold the object's pixels byte-identical and change only what
surrounds them. They are the regression guard for the property the runbook and
the demo both assume: **object, not environment.**

They also hold the other half, because loosening the positive side is free if
nobody checks the negative one: an empty scene and a different object must
still score essentially nothing.
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

HEIGHT, WIDTH = 240, 320
OBJECT_TOP, OBJECT_LEFT = 70, 100


def matcher() -> ObjectCueMatcher:
    return ObjectCueMatcher(
        min_reference_keypoints=10,
        min_frame_descriptors=10,
        min_good_matches=50,
        min_inliers=30,
    )


def an_object() -> np.ndarray:
    """Dark and textured: solid enough for the two-shot diff to isolate."""
    return np.random.default_rng(4).integers(35, 90, (90, 110, 3)).astype(np.uint8)


def plain_wall(level: int) -> np.ndarray:
    return np.full((HEIGHT, WIDTH, 3), level, np.uint8)


def another_room(seed: int, base: int, spread: int) -> np.ndarray:
    """A wall that is not the binding wall: a gradient plus mild grain."""
    rng = np.random.default_rng(seed)
    gradient = (
        np.linspace(-spread, spread, WIDTH)[None, :]
        + np.linspace(-spread, spread, HEIGHT)[:, None]
    )
    grain = rng.normal(0, 4, (HEIGHT, WIDTH))
    level = np.clip(base + gradient + grain, 0, 255).astype(np.uint8)
    return cv2.cvtColor(level, cv2.COLOR_GRAY2BGR)


def held_up_against(background: np.ndarray, obj: np.ndarray) -> np.ndarray:
    scene = background.copy()
    height, width = obj.shape[:2]
    scene[OBJECT_TOP : OBJECT_TOP + height, OBJECT_LEFT : OBJECT_LEFT + width] = obj
    return scene


class BackgroundIndependenceTests(unittest.TestCase):
    def setUp(self):
        self.matcher = matcher()
        self.object = an_object()
        self.binding_wall = plain_wall(128)

        empty = self.binding_wall
        present = held_up_against(empty, self.object)
        self.state = self.matcher.object_reference_state(empty, present)
        self.assertIsNotNone(self.state, "the capture itself was refused")
        self.good_bar, self.inlier_bar = self.matcher.effective_thresholds(self.state)

    def _score(self, image):
        return self.matcher.score_frame(self.state, self.matcher.to_gray(image))

    def _assert_matches(self, image, description):
        scored = self._score(image)
        self.assertGreater(
            scored["good_matches"],
            self.good_bar,
            f"{description}: good matches {scored['good_matches']} "
            f"did not clear {self.good_bar}",
        )
        self.assertGreater(
            scored["inliers"],
            self.inlier_bar,
            f"{description}: inliers {scored['inliers']} did not clear {self.inlier_bar}",
        )

    def test_it_matches_against_the_wall_it_was_bound_against(self):
        self._assert_matches(
            held_up_against(self.binding_wall, self.object), "same wall"
        )

    def test_it_matches_when_the_wall_is_dimmer(self):
        self._assert_matches(
            held_up_against(plain_wall(60), self.object), "dimmer wall"
        )

    def test_it_matches_when_the_wall_is_brighter(self):
        self._assert_matches(
            held_up_against(plain_wall(200), self.object), "brighter wall"
        )

    def test_it_matches_in_a_room_it_was_never_bound_in(self):
        """The reported failure, as a test."""
        for seed, base, spread, name in (
            (1, 170, 25, "light wall"),
            (2, 70, 25, "dark wall"),
            (3, 120, 60, "patterned wall"),
        ):
            with self.subTest(room=name):
                self._assert_matches(
                    held_up_against(another_room(seed, base, spread), self.object),
                    name,
                )

    def test_the_object_is_what_carries_it_and_not_its_position(self):
        """Held a little differently, which is what a person does."""
        shifted = another_room(1, 170, 25)
        height, width = self.object.shape[:2]
        top, left = OBJECT_TOP - 18, OBJECT_LEFT + 24
        shifted[top : top + height, left : left + width] = self.object
        self._assert_matches(shifted, "moved within the frame")


class TheNegativeSideStillHoldsTests(unittest.TestCase):
    """Whatever is done to help the object match must not help anything else."""

    def setUp(self):
        self.matcher = matcher()
        self.object = an_object()
        wall = plain_wall(128)
        self.state = self.matcher.object_reference_state(
            wall, held_up_against(wall, self.object)
        )
        self.good_bar, self.inlier_bar = self.matcher.effective_thresholds(self.state)

    def _refuses(self, image, description):
        scored = self.matcher.score_frame(self.state, self.matcher.to_gray(image))
        clears = (
            scored["good_matches"] > self.good_bar
            and scored["inliers"] > self.inlier_bar
        )
        self.assertFalse(
            clears,
            f"{description} was accepted: good {scored['good_matches']}, "
            f"inliers {scored['inliers']}",
        )

    def test_the_empty_binding_scene_is_refused(self):
        """The defect #184 existed to close, re-checked after changing to_gray."""
        self._refuses(plain_wall(128), "the empty scene it was bound against")

    def test_an_empty_room_it_was_never_bound_in_is_refused(self):
        self._refuses(another_room(3, 120, 60), "an empty unfamiliar room")

    def test_a_different_object_is_refused(self):
        other = (
            np.random.default_rng(77).integers(35, 90, (90, 110, 3)).astype(np.uint8)
        )
        self._refuses(
            held_up_against(plain_wall(128), other), "a different object, same place"
        )


class TemplatesFromAnotherDescriptorSpaceTests(unittest.TestCase):
    """A template cut from a different grayscale is unbound, not broken.

    Descriptors only compare within the space they were cut from. Loading one
    from an older build and leaving it in place would produce a Face that looks
    bound and never matches - which is indistinguishable, to an operator, from
    the defect this change fixes.
    """

    def test_the_store_declares_which_space_it_wrote(self):
        from phasmid.object_cue_store import ObjectCueStore

        self.assertEqual(ObjectCueStore.DESCRIPTOR_SPACE, 2)


if __name__ == "__main__":
    unittest.main()
