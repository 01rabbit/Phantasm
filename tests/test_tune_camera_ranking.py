"""The sweep must not recommend something the device cannot run.

Both rules here come from a run on the device that broke them, and the numbers
below are that run's.

The keypoint count saturated. The gate's detector caps at `nfeatures=1000`,
which is the right cap for matching and the wrong one for comparing settings:
640x480 reported 919 and every resolution above it reported exactly 1000. That
reads as "bigger is better" when it means "the ruler ended here". The probe now
counts with the cap lifted, and ties are broken rather than resolved by list
order.

And the frame budget was ignored. 1024x768 cost 272 ms per frame against a
250 ms interval at four frames a second - and the sweep measures less work than
the console does, since it never matches, encodes or draws. The old ranking
recommended it anyway, immediately above its own printed warning not to. More
pixels than the device can process is not more cue: the match history needs
several consecutive frames, and a frame that arrives late has not arrived.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))

_spec = importlib.util.spec_from_file_location(
    "tune_camera", os.path.join(ROOT, "scripts", "pi_zero2w", "tune_camera.py")
)
tune_camera = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tune_camera)


def reading(keypoints: int, sharpness: float, interval_ms: float) -> dict:
    return {
        "keypoints": keypoints,
        "sharpness": sharpness,
        "interval_ms": interval_ms,
        "focus": "continuous",
        "applied": [],
    }


class FrameBudgetTests(unittest.TestCase):
    def test_a_configuration_over_the_budget_is_not_recommended(self):
        """The device's own resolution sweep, replayed."""
        measured = {
            "640x480": reading(919, 1109.1, 113.0),
            "1024x768": reading(1000, 828.8, 272.0),
            "1280x960": reading(1000, 443.1, 391.0),
        }
        chosen, _ = tune_camera.sweep(
            "resolution",
            [(label, label) for label in measured],
            lambda option: measured[option],
        )
        self.assertEqual(chosen, "640x480")

    def test_when_nothing_fits_the_cheapest_is_offered_rather_than_nothing(self):
        measured = {
            "big": reading(1000, 900.0, 400.0),
            "bigger": reading(1000, 950.0, 900.0),
        }
        chosen, _ = tune_camera.sweep(
            "resolution",
            [(label, label) for label in measured],
            lambda option: measured[option],
        )
        self.assertEqual(chosen, "big")

    def test_the_budget_leaves_room_for_the_work_the_sweep_does_not_do(self):
        """Matching, encoding and drawing all land on top of what is measured."""
        self.assertLess(tune_camera.FRAME_BUDGET_MS, 250.0)


class SaturationTests(unittest.TestCase):
    def test_a_tie_is_broken_by_detail_not_by_list_order(self):
        """The device's sharpness sweep: all three saturated at 1000.

        The old ranking answered 1.0 - the first of the three - while its own
        second column said 2.5 had half again as much detail.
        """
        measured = {
            "1.0": reading(1000, 1245.3, 113.0),
            "1.5": reading(1000, 1254.9, 113.0),
            "2.5": reading(1000, 1353.3, 113.0),
        }
        chosen, _ = tune_camera.sweep(
            "sharpness",
            [(label, label) for label in measured],
            lambda option: measured[option],
        )
        self.assertEqual(chosen, "2.5")

    def test_the_probe_counts_past_the_cap_the_gate_stops_at(self):
        """Otherwise the measurement ends exactly where the question starts."""
        self.assertGreater(tune_camera.PROBE.getMaxFeatures(), 1000)

    def test_a_real_difference_still_wins_over_detail(self):
        """Sharpness is the tie-break, not the criterion."""
        measured = {
            "more keypoints": reading(900, 500.0, 100.0),
            "sharper": reading(400, 2000.0, 100.0),
        }
        chosen, _ = tune_camera.sweep(
            "resolution",
            [(label, label) for label in measured],
            lambda option: measured[option],
        )
        self.assertEqual(chosen, "more keypoints")


class NothingMeasuredTests(unittest.TestCase):
    def test_zeros_are_refused_rather_than_ranked(self):
        measured = {"a": reading(0, 0.0, 0.0), "b": reading(0, 0.0, 0.0)}
        with self.assertRaises(tune_camera.CameraDeliveredNothing):
            tune_camera.sweep(
                "resolution",
                [(label, label) for label in measured],
                lambda option: measured[option],
            )


if __name__ == "__main__":
    unittest.main()
