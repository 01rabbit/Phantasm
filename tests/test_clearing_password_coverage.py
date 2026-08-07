"""Doctor reports how many entries can be ended, never which one.

The two environment variables Doctor already warns about fire without the
operator doing anything (#182). A clearing password is different: it fires only
when that specific password is typed, so a Face without one is a setup state,
not an armed hazard - reported as INFO, not WARN.

The mistake it exists to catch is the one that happened on the device: a
clearing password set on one Face and not the other, discovered only when the
missing one was needed. At that point "never set" and "wrong password" are
indistinguishable *by design* - the clearing path gives nothing away on failure
(#191) - so the only place the difference can surface is here, beforehand.

What it must not do is say which Face. That is what the sealed registry sidecar
exists to keep out of readable state (#180), and a side effect worth having was
that a purged Face reads identically to a never-used one. A per-Face list would
partly undo that for anyone who can run Doctor.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))

from phasmid.models.doctor import DoctorLevel
from phasmid.services.access_cue_service import access_cue_service
from phasmid.services.doctor_service import _check_clearing_password_coverage
from phasmid.services.vessel_workflow_service import VesselWorkflowService


class ClearingPasswordCoverageTests(unittest.TestCase):
    def setUp(self):
        self._dirs = tempfile.TemporaryDirectory()
        self._env = mock.patch.dict(
            os.environ,
            {
                "PHASMID_CONFIG_DIR": os.path.join(self._dirs.name, "config"),
                "PHASMID_STATE_DIR": os.path.join(self._dirs.name, "state"),
                "PHASMID_FIELD_MODE": "0",
            },
        )
        self._env.start()
        self.addCleanup(self._dirs.cleanup)
        self.addCleanup(self._env.stop)

        self.service = VesselWorkflowService()
        self.vessel = Path(self._dirs.name) / "demo.vessel"
        self.service.create_vessel(self.vessel, "8M")
        self.modes = access_cue_service.modes()

    def _set_up_face(self, selector, mode, password, clearing=None):
        self.service.add_payload(
            self.vessel,
            f"{selector}.txt",
            b"contents",
            password,
            restricted_passphrase=clearing,
            selector=selector,
            cue_sequence=access_cue_service.sequence_for_mode(mode),
        )

    def test_nothing_set_up_yet(self):
        check = _check_clearing_password_coverage()
        self.assertEqual(check.level, DoctorLevel.INFO)
        self.assertIn("No protected entries", check.message)

    def test_every_set_up_entry_covered(self):
        self._set_up_face("face_a", self.modes[0], "pw-a", clearing="clear-a")
        self._set_up_face("face_b", self.modes[1], "pw-b", clearing="clear-b")
        check = _check_clearing_password_coverage()
        self.assertEqual(check.level, DoctorLevel.OK)
        self.assertIn("All 2", check.message)

    def test_one_covered_and_one_not(self):
        """The reported failure, caught before it matters."""
        self._set_up_face("face_a", self.modes[0], "pw-a", clearing="clear-a")
        self._set_up_face("face_b", self.modes[1], "pw-b")
        check = _check_clearing_password_coverage()
        self.assertEqual(check.level, DoctorLevel.INFO)
        self.assertIn("1 of 2", check.message)

    def test_it_never_names_which_entry(self):
        self._set_up_face("face_a", self.modes[0], "pw-a", clearing="clear-a")
        self._set_up_face("face_b", self.modes[1], "pw-b")
        reported = f"{_check_clearing_password_coverage().message} " + str(
            _check_clearing_password_coverage().detail or ""
        )
        for naming in (
            "face_a",
            "face_b",
            "Slot A",
            "Slot B",
            "Entry 1",
            "Entry 2",
            "first",
            "second",
        ):
            with self.subTest(naming=naming):
                self.assertNotIn(naming, reported)

    def test_a_face_that_was_never_set_up_is_not_counted_as_a_gap(self):
        """An entry with no credentials has nothing to end."""
        self._set_up_face("face_a", self.modes[0], "pw-a", clearing="clear-a")
        check = _check_clearing_password_coverage()
        self.assertEqual(check.level, DoctorLevel.OK)
        self.assertNotIn("of 2", check.message)

    def test_field_mode_says_nothing(self):
        """A surface read under observation says less about what is configured."""
        self._set_up_face("face_a", self.modes[0], "pw-a", clearing="clear-a")
        self._set_up_face("face_b", self.modes[1], "pw-b")
        with mock.patch.dict(os.environ, {"PHASMID_FIELD_MODE": "1"}):
            check = _check_clearing_password_coverage()
        self.assertEqual(check.level, DoctorLevel.INFO)
        self.assertNotIn("1 of 2", check.message)

    def test_it_is_never_a_warning(self):
        """Nothing here fires without the operator typing that password."""
        self._set_up_face("face_a", self.modes[0], "pw-a", clearing="clear-a")
        self._set_up_face("face_b", self.modes[1], "pw-b")
        self.assertIn(
            _check_clearing_password_coverage().level,
            (DoctorLevel.OK, DoctorLevel.INFO),
        )


class CoverageCountTests(unittest.TestCase):
    """The service-level counts the check reads."""

    def setUp(self):
        self._dirs = tempfile.TemporaryDirectory()
        self._env = mock.patch.dict(
            os.environ,
            {
                "PHASMID_CONFIG_DIR": os.path.join(self._dirs.name, "config"),
                "PHASMID_STATE_DIR": os.path.join(self._dirs.name, "state"),
            },
        )
        self._env.start()
        self.addCleanup(self._dirs.cleanup)
        self.addCleanup(self._env.stop)
        self.service = VesselWorkflowService()
        self.vessel = Path(self._dirs.name) / "demo.vessel"
        self.service.create_vessel(self.vessel, "8M")

    def test_a_fresh_vessel_counts_nothing(self):
        self.assertEqual(self.service.clearing_password_coverage(self.vessel), (0, 0))

    def test_a_face_without_a_clearing_password_counts_as_uncovered(self):
        self.service.add_payload(
            self.vessel,
            "a.txt",
            b"contents",
            "pw-a",
            selector="face_a",
            cue_sequence=access_cue_service.sequence_for_mode(
                access_cue_service.modes()[0]
            ),
        )
        self.assertEqual(self.service.clearing_password_coverage(self.vessel), (1, 0))


if __name__ == "__main__":
    unittest.main()
