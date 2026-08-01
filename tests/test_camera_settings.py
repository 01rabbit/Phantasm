"""The camera is configured, not merely opened.

For most of this project's life the camera was opened with exactly one control
set on it — `FrameDurationLimits` — and everything else left at whatever the ISP
defaults to for photographs a person will look at. That is not the same thing as
an image a corner detector can work with, and none of the gaps announced
themselves:

* the lens stayed wherever it powered up, so a desk-distance object was soft;
* the shutter was free to run to 200 ms, so a hand-held object smeared;
* denoising smoothed away the fine structure ORB calls a corner;
* white balance drifted under the grayscale conversion, moving descriptors.

Every one of those presents as "the object will not bind" or "the object will
not match", which is where the search went instead. These tests hold the
settings that close them, and hold the *shape* of how they are applied: asked
for against what the module reports, never assumed.
"""

from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))

from phasmid import config
from phasmid.camera_frame_source import CameraFrameSource


class FrameSizeTests(unittest.TestCase):
    """Resolution is the ceiling on everything downstream.

    Measured on a printed packet filling about 30% of the frame width, in
    focus: 24 template keypoints at 320x240, 572 at 640x480, 823 at 1024x768.
    A template needs 60 of its own to be bound at all, so the old default could
    not bind that object no matter what else was correct.
    """

    def test_the_default_is_not_the_old_postage_stamp(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PHASMID_CAMERA_SIZE", None)
            self.assertEqual(config.camera_frame_size(), (640, 480))

    def test_a_device_can_ask_for_more_or_less(self):
        with mock.patch.dict(os.environ, {"PHASMID_CAMERA_SIZE": "1280x960"}):
            self.assertEqual(config.camera_frame_size(), (1280, 960))

    def test_nonsense_falls_back_rather_than_raising(self):
        for value in ("", "wide", "640", "640x", "0x0", "12x12"):
            with self.subTest(value=value):
                with mock.patch.dict(os.environ, {"PHASMID_CAMERA_SIZE": value}):
                    self.assertEqual(config.camera_frame_size(), (640, 480))


class ExposureCeilingTests(unittest.TestCase):
    """A 200 ms shutter and a hand-held object do not go together.

    Measured on a 572-keypoint template: a 3 px smear — about a 33 ms shutter —
    scores 197 good matches, a 9 px smear about 70, a 21 px smear 22 and is
    refused.
    """

    def test_the_default_caps_the_shutter_well_under_the_old_value(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PHASMID_CAMERA_MAX_EXPOSURE_US", None)
            self.assertEqual(config.camera_max_exposure_us(), 33000)
            self.assertLess(config.camera_max_exposure_us(), 200000)

    def test_a_dim_room_can_ask_for_a_longer_one(self):
        with mock.patch.dict(os.environ, {"PHASMID_CAMERA_MAX_EXPOSURE_US": "66000"}):
            self.assertEqual(config.camera_max_exposure_us(), 66000)


class DetailSettingTests(unittest.TestCase):
    def test_denoising_defaults_to_minimal(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PHASMID_CAMERA_DENOISE", None)
            self.assertEqual(config.camera_denoise(), "minimal")

    def test_sharpness_defaults_above_the_camera_default(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PHASMID_CAMERA_SHARPNESS", None)
            self.assertGreater(config.camera_sharpness(), 1.0)

    def test_sharpness_is_bounded_rather_than_trusted(self):
        for value, expected in (("-5", 0.0), ("999", 16.0), ("nonsense", 1.5)):
            with self.subTest(value=value):
                with mock.patch.dict(os.environ, {"PHASMID_CAMERA_SHARPNESS": value}):
                    self.assertEqual(config.camera_sharpness(), expected)

    def test_white_balance_is_locked_by_default(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PHASMID_CAMERA_LOCK_AWB", None)
            self.assertTrue(config.camera_lock_white_balance())


class ControlsAreOfferedNotAssumedTests(unittest.TestCase):
    """A module that does not support a control must still open.

    Camera modules differ — a fixed-focus one has no `AfMode` at all — so every
    control is offered against what the module reports. Assuming a sensor is
    how a working camera turns into a camera that will not start.
    """

    def setUp(self):
        self.camera = CameraFrameSource(frame_size=(640, 480), fps=4)

    def test_a_camera_reporting_nothing_yields_no_controls(self):
        with mock.patch.object(self.camera, "_supported_controls", return_value={}):
            controls = self.camera._build_controls()
        self.assertEqual(controls, {})
        self.assertEqual(self.camera.applied_controls, [])

    def test_a_fixed_focus_module_is_left_alone(self):
        with mock.patch.object(
            self.camera, "_supported_controls", return_value={"FrameDurationLimits": 1}
        ):
            self.camera._build_controls()
        self.assertEqual(self.camera.focus_mode, "fixed lens")

    def test_the_exposure_ceiling_reaches_the_camera(self):
        with mock.patch.dict(os.environ, {"PHASMID_CAMERA_MAX_EXPOSURE_US": "20000"}):
            with mock.patch.object(
                self.camera,
                "_supported_controls",
                return_value={"FrameDurationLimits": 1},
            ):
                controls = self.camera._build_controls()
        self.assertEqual(controls["FrameDurationLimits"][1], 20000)
        self.assertIn("exposure-ceiling", self.camera.applied_controls)

    def test_focus_can_be_switched_off_without_touching_the_lens(self):
        with mock.patch.dict(os.environ, {"PHASMID_CAMERA_FOCUS": "off"}):
            with mock.patch.object(
                self.camera, "_supported_controls", return_value={"AfMode": 1}
            ):
                controls = self.camera._build_controls()
        self.assertNotIn("AfMode", controls)
        self.assertIn("off", self.camera.focus_mode)

    def test_what_was_applied_is_reported(self):
        """ "The camera ignored half of this" must not look like success."""
        with mock.patch.object(
            self.camera, "_supported_controls", return_value={"FrameDurationLimits": 1}
        ):
            self.camera._build_controls()
        status = self.camera.status()
        self.assertIn("applied_controls", status)
        self.assertIn("focus_mode", status)


class RefocusTests(unittest.TestCase):
    """The capture that becomes a template gets its own focus sweep."""

    def test_it_is_a_no_op_without_a_camera(self):
        camera = CameraFrameSource(frame_size=(640, 480), fps=4)
        self.assertFalse(camera.refocus(settle_seconds=0))


if __name__ == "__main__":
    unittest.main()
