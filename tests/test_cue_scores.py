"""The scores shown on the preview are the scores the gate acts on.

The overlay exists because a badge that says only yes or no cannot be aimed
against. Aiming a camera is iterative — closer, turned, relit — and each step
needs to know whether it helped. But a diagnostic that reports numbers other
than the ones the gate decides on is worse than no diagnostic, because it is
believed: it would send an operator on stage having tuned against a
measurement that was never the one being applied.

So `score_frame` has to agree with `match_reference_state` about the same
frame, in both directions — where it matches and where it does not — and both
have to be reading the same Lowe ratio and RANSAC tolerance rather than each
carrying its own copy of 0.75 and 5.0 — including when a device overrides them.
"""

from __future__ import annotations

import os
import sys
import unittest

import numpy as np

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))

from phasmid.object_cue_matcher import ObjectCueMatcher


def build_matcher() -> ObjectCueMatcher:
    return ObjectCueMatcher(
        min_reference_keypoints=10,
        min_frame_descriptors=10,
        min_good_matches=50,
        min_inliers=30,
    )


def textured(seed: int, shape=(240, 320, 3)) -> np.ndarray:
    """An image ORB can find plenty of keypoints in."""
    return np.random.default_rng(seed).integers(0, 255, shape).astype(np.uint8)


class ScoreAgreesWithMatchTests(unittest.TestCase):
    def setUp(self):
        self.matcher = build_matcher()
        self.image = textured(11)
        self.state = self.matcher.reference_state_from_image(self.image)
        self.assertIsNotNone(self.state["des"])

    def test_the_scores_are_the_ones_the_gate_matched_on(self):
        gray = self.matcher.to_gray(self.image)
        matched = self.matcher.match_reference_state(self.state, gray)
        scored = self.matcher.score_frame(self.state, gray)
        self.assertIsNotNone(matched, "the identical frame should match")
        self.assertEqual(scored["good_matches"], matched["good_matches"])
        self.assertEqual(scored["inliers"], matched["inliers"])
        self.assertEqual(
            scored["required_good_matches"], matched["required_good_matches"]
        )
        self.assertEqual(scored["required_inliers"], matched["required_inliers"])

    def test_a_frame_the_gate_refuses_scores_below_the_bar(self):
        """The direction that matters: a refusal has to read as a refusal."""
        gray = self.matcher.to_gray(textured(999))
        self.assertIsNone(self.matcher.match_reference_state(self.state, gray))
        scored = self.matcher.score_frame(self.state, gray)
        self.assertIsNotNone(scored, "an unrelated frame still deserves a number")
        clears = (
            scored["good_matches"] > scored["required_good_matches"]
            and scored["inliers"] > scored["required_inliers"]
        )
        self.assertFalse(clears)

    def test_it_reports_the_bar_the_thresholds_produce(self):
        good, inliers = self.matcher.effective_thresholds(self.state)
        scored = self.matcher.score_frame(self.state, self.matcher.to_gray(self.image))
        self.assertEqual(scored["required_good_matches"], good)
        self.assertEqual(scored["required_inliers"], inliers)
        self.assertEqual(scored["keypoints"], len(self.state["kp"]))

    def test_nothing_bound_scores_nothing(self):
        empty = self.matcher.empty_reference()
        gray = self.matcher.to_gray(self.image)
        self.assertIsNone(self.matcher.score_frame(empty, gray))

    def test_a_blank_frame_scores_zero_rather_than_failing(self):
        blank = np.full((240, 320, 3), 128, np.uint8)
        scored = self.matcher.score_frame(self.state, self.matcher.to_gray(blank))
        self.assertEqual(scored["good_matches"], 0)
        self.assertEqual(scored["inliers"], 0)

    def test_scoring_by_descriptors_matches_scoring_by_frame(self):
        """The overlay path extracts features once for every entry."""
        gray = self.matcher.to_gray(self.image)
        kp, des = self.matcher.orb.detectAndCompute(gray, None)
        self.assertEqual(
            self.matcher.score_descriptors(self.state, kp, des),
            self.matcher.score_frame(self.state, gray),
        )


class SharedConstantsTests(unittest.TestCase):
    """Both paths read one Lowe ratio and one RANSAC tolerance."""

    def test_changing_the_lowe_ratio_moves_both_paths(self):
        matcher = build_matcher()
        image = textured(5)
        state = matcher.reference_state_from_image(image)

        # A slightly noisy frame rather than the identical one: an exact match
        # scores distance 0, which passes any ratio at all and would make this
        # look constant no matter what the constant said.
        rng = np.random.default_rng(5)
        noisy = np.clip(image.astype(int) + rng.integers(-8, 9, image.shape), 0, 255)
        gray = matcher.to_gray(noisy.astype(np.uint8))

        before = matcher.score_frame(state, gray)["good_matches"]
        matcher.lowe_ratio = 0.05
        after = matcher.score_frame(state, gray)
        self.assertLess(after["good_matches"], before, "the constant is not being read")

        # The point of the test: the gate saw exactly the same thing, because
        # there is one constant and not two copies of 0.75. A ratio this tight
        # may drop the frame below the bar entirely, which is still agreement -
        # what must not happen is the gate matching on a count the score does
        # not report.
        gated = matcher.match_reference_state(state, gray)
        if gated is None:
            self.assertLessEqual(after["good_matches"], after["required_good_matches"])
        else:
            self.assertEqual(gated["good_matches"], after["good_matches"])


class TuningKnobTests(unittest.TestCase):
    """The two knobs a device with awkward light or a 3-D prop actually needs.

    Both were literals inside the matching path. They are the ones that matter
    when the proportional thresholds cannot help: the Lowe ratio decides what
    counts as the same feature, so it is the knob for light that has moved
    since the object was bound, and the RANSAC tolerance decides how far a
    correspondence may sit from the fitted plane, which is what a non-planar
    object strains when it is turned.
    """

    def test_a_looser_lowe_ratio_admits_more_matches(self):
        loose = ObjectCueMatcher(
            min_reference_keypoints=10,
            min_frame_descriptors=10,
            min_good_matches=50,
            min_inliers=30,
            lowe_ratio=0.9,
        )
        tight = ObjectCueMatcher(
            min_reference_keypoints=10,
            min_frame_descriptors=10,
            min_good_matches=50,
            min_inliers=30,
            lowe_ratio=0.5,
        )
        image = textured(21)
        rng = np.random.default_rng(21)
        noisy = np.clip(image.astype(int) + rng.integers(-10, 11, image.shape), 0, 255)
        gray = loose.to_gray(noisy.astype(np.uint8))
        state = loose.reference_state_from_image(image)

        self.assertGreater(
            loose.score_frame(state, gray)["good_matches"],
            tight.score_frame(state, gray)["good_matches"],
        )

    def test_the_defaults_are_the_shipped_constants(self):
        matcher = build_matcher()
        self.assertEqual(matcher.lowe_ratio, ObjectCueMatcher.LOWE_RATIO)
        self.assertEqual(
            matcher.ransac_reprojection, ObjectCueMatcher.RANSAC_REPROJECTION
        )

    def test_the_knobs_reach_the_gate_and_not_only_the_diagnostic(self):
        """A knob that only moved the report would be worse than no knob."""
        matcher = build_matcher()
        image = textured(33)
        state = matcher.reference_state_from_image(image)
        rng = np.random.default_rng(33)
        noisy = np.clip(image.astype(int) + rng.integers(-10, 11, image.shape), 0, 255)
        gray = matcher.to_gray(noisy.astype(np.uint8))

        matcher.lowe_ratio = 0.5
        tightened = matcher.match_reference_state(state, gray)
        matcher.lowe_ratio = 0.9
        loosened = matcher.match_reference_state(state, gray)
        self.assertGreater(loosened["good_matches"], tightened["good_matches"])


if __name__ == "__main__":
    unittest.main()
