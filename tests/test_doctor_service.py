"""Tests for the operator diagnostics checks."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from contextlib import contextmanager
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))

from phasmid.models.doctor import DoctorLevel
from phasmid.services.doctor_service import run_doctor_checks

_ADVISORY_ENV = ("PHASMID_DUMMY_PROFILE_DIR", "PHASMID_DUMMY_CONTAINER_PATH")


@contextmanager
def _isolated_host(tmpdir: str, **env: str):
    """Run the doctor against fixtures only, never the machine it runs on.

    ``run_doctor_checks`` reads the real config directory and resolves
    ``vault.bin`` relative to the process working directory. Left alone, the
    warning set then depends on whether this particular machine happens to
    have a permissive ~/.config/phasmid or a stray vault.bin next to the
    checkout - which makes a green run mean nothing and a red one mean
    nothing either.
    """
    cwd = os.getcwd()
    patched = {
        "PHASMID_STATE_DIR": tmpdir,
        "PHASMID_CONFIG_DIR": os.path.join(tmpdir, "config"),
        **env,
    }
    os.makedirs(patched["PHASMID_CONFIG_DIR"], mode=0o700, exist_ok=True)
    os.makedirs(
        os.path.join(patched["PHASMID_CONFIG_DIR"], "profiles"),
        mode=0o700,
        exist_ok=True,
    )
    try:
        os.chdir(tmpdir)
        with mock.patch.dict(os.environ, patched, clear=False):
            for name in _ADVISORY_ENV:
                if name not in env:
                    os.environ.pop(name, None)
            yield
    finally:
        os.chdir(cwd)


def test_unconfigured_advisory_reports_nothing_rather_than_warning():
    """The advisory only applies to material the operator points it at.

    PHASMID_DUMMY_PROFILE_DIR and PHASMID_DUMMY_CONTAINER_PATH are operator
    settings. Left unset they name paths no operation writes, so the four
    checks warned on every device forever and the warnings could not be acted
    on - and they read as a verdict on the operator's cover story, which the
    tool has no way to judge.

    The checks stay (a configured operator still gets the advisory) but an
    advisory nobody asked for is not a finding.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        with _isolated_host(tmpdir):
            result = run_doctor_checks()

    advisory = [c for c in result.checks if "Dummy Profile" in c.name]
    assert len(advisory) == 5, [c.name for c in result.checks]
    assert all(c.level != DoctorLevel.WARN for c in advisory), [
        (c.name, c.level.value) for c in advisory
    ]
    assert all(c.message == "not configured" for c in advisory)


def test_an_ordinary_vault_bin_does_not_switch_the_advisory_on():
    """The container default is ``vault.bin`` - the CLI's default vessel name.

    Gating on whether that path exists handed the whole warning storm back to
    any operator who had ever stored a file without naming a Vessel. The
    operator's intent lives in the environment variables, not in the
    filesystem.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        with _isolated_host(tmpdir):
            with open(os.path.join(tmpdir, "vault.bin"), "wb") as handle:
                handle.write(b"x" * 4096)
            result = run_doctor_checks()

    advisory = [c for c in result.checks if "Dummy Profile" in c.name]
    assert all(c.message == "not configured" for c in advisory), [
        (c.name, c.message) for c in advisory
    ]


def test_blank_advisory_settings_count_as_unset():
    """Blanking a variable is how an operator turns a setting off.

    ``Path("")`` is the working directory, which exists everywhere, so
    treating a blank value as a configured path measures whatever directory
    the console was launched from and reports its size as the container's.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        with _isolated_host(
            tmpdir,
            PHASMID_DUMMY_PROFILE_DIR="",
            PHASMID_DUMMY_CONTAINER_PATH="   ",
        ):
            result = run_doctor_checks()

    advisory = [c for c in result.checks if "Dummy Profile" in c.name]
    assert all(c.message == "not configured" for c in advisory), [
        (c.name, c.message) for c in advisory
    ]


def test_configured_advisory_still_reports_a_shortfall():
    """Pointed at real material it must still do its job."""
    with tempfile.TemporaryDirectory() as tmpdir:
        profile_dir = os.path.join(tmpdir, "prepared")
        os.makedirs(profile_dir)
        with open(os.path.join(profile_dir, "a.bin"), "wb") as handle:
            handle.write(b"a" * 64)
        container = os.path.join(tmpdir, "container.bin")
        with open(container, "wb") as handle:
            handle.write(b"b" * (10 * 1024 * 1024))

        with _isolated_host(
            tmpdir,
            PHASMID_DUMMY_PROFILE_DIR=profile_dir,
            PHASMID_DUMMY_CONTAINER_PATH=container,
            PHASMID_DUMMY_MIN_SIZE_MB="1",
            PHASMID_DUMMY_MIN_FILE_COUNT="2",
            PHASMID_DUMMY_OCCUPANCY_WARN="0.10",
        ):
            result = run_doctor_checks()

    verdict = next(c for c in result.checks if c.name == "Dummy Profile Plausibility")
    assert verdict.level == DoctorLevel.WARN
    # Volume, not believability: the tool cannot judge a cover story.
    assert "convincing" not in verdict.message.lower()
    assert "volume" in verdict.message.lower()


def test_a_fresh_host_warns_only_about_genuine_host_facts():
    """The warning count is a talking point, so it has to be honest."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with _isolated_host(tmpdir):
            result = run_doctor_checks()

    warns = [c for c in result.checks if c.level == DoctorLevel.WARN]
    assert all("Dummy Profile" not in c.name for c in warns), [c.name for c in warns]
    assert all(
        c.name in {"Temporary Directory", "Swap", "Compressed Swap", "Shell History"}
        for c in warns
    ), [c.name for c in warns]


class AutoDestructionCheckTests(unittest.TestCase):
    """Doctor must surface the settings that destroy a Face during a read.

    A TestCase rather than the module-level functions above, because CI runs
    `python -m unittest discover`, which does not collect bare test functions -
    a safety check nobody verifies on the way in is not much of a safety check.
    """

    def _check(self, **env: str):
        with tempfile.TemporaryDirectory() as tmpdir:
            with _isolated_host(tmpdir, **env):
                result = run_doctor_checks()
        return next(c for c in result.checks if c.name == "Automatic Destruction")

    def test_reported_as_off_by_default(self):
        check = self._check()
        self.assertEqual(check.level, DoctorLevel.OK, check.message)

    def test_duress_mode_is_surfaced_as_a_destruction_warning(self):
        """With this on, opening the disclosure Face destroys the other one."""
        check = self._check(PHASMID_DURESS_MODE="1")
        self.assertEqual(check.level, DoctorLevel.WARN)
        self.assertIn("PHASMID_DURESS_MODE", check.message)
        self.assertIn("destroys the other", check.message)

    def test_disabling_purge_confirmation_is_surfaced_too(self):
        check = self._check(PHASMID_PURGE_CONFIRMATION="0")
        self.assertEqual(check.level, DoctorLevel.WARN)
        self.assertIn("PHASMID_PURGE_CONFIRMATION", check.message)

    def test_both_settings_are_reported_together(self):
        """Reporting only the first would leave the second armed after a fix."""
        check = self._check(PHASMID_DURESS_MODE="1", PHASMID_PURGE_CONFIRMATION="0")
        self.assertEqual(check.level, DoctorLevel.WARN)
        self.assertIn("PHASMID_DURESS_MODE", check.message)
        self.assertIn("PHASMID_PURGE_CONFIRMATION", check.message)
