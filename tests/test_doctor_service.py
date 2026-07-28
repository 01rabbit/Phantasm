"""Tests for the operator diagnostics checks."""

from __future__ import annotations

import os
import sys
import tempfile
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))

from phasmid.models.doctor import DoctorLevel
from phasmid.services.doctor_service import run_doctor_checks


def test_unconfigured_advisory_reports_nothing_rather_than_warning():
    """The advisory only applies to material the operator points it at.

    PHASMID_DUMMY_PROFILE_DIR and PHASMID_DUMMY_CONTAINER_PATH are operator
    settings. Left at their defaults they name paths no operation writes, so
    the four checks warned on every device forever and the warnings could
    not be acted on - and they read as a verdict on the operator's cover
    story, which the tool has no way to judge.

    The checks stay (a configured operator still gets the advisory) but an
    advisory nobody asked for is not a finding.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        with mock.patch.dict(
            os.environ,
            {
                "PHASMID_STATE_DIR": tmpdir,
                "PHASMID_DUMMY_PROFILE_DIR": os.path.join(tmpdir, "absent"),
                "PHASMID_DUMMY_CONTAINER_PATH": os.path.join(tmpdir, "absent.bin"),
            },
            clear=False,
        ):
            result = run_doctor_checks()

    advisory = [c for c in result.checks if "Dummy Profile" in c.name]
    assert len(advisory) == 5, [c.name for c in result.checks]
    assert all(c.level != DoctorLevel.WARN for c in advisory), [
        (c.name, c.level.value) for c in advisory
    ]
    assert all(c.message == "not configured" for c in advisory)


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

        with mock.patch.dict(
            os.environ,
            {
                "PHASMID_STATE_DIR": tmpdir,
                "PHASMID_DUMMY_PROFILE_DIR": profile_dir,
                "PHASMID_DUMMY_CONTAINER_PATH": container,
                "PHASMID_DUMMY_MIN_SIZE_MB": "1",
                "PHASMID_DUMMY_MIN_FILE_COUNT": "2",
                "PHASMID_DUMMY_OCCUPANCY_WARN": "0.10",
            },
            clear=False,
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
        with mock.patch.dict(
            os.environ,
            {
                "PHASMID_STATE_DIR": tmpdir,
                "PHASMID_DUMMY_PROFILE_DIR": os.path.join(tmpdir, "absent"),
                "PHASMID_DUMMY_CONTAINER_PATH": os.path.join(tmpdir, "absent.bin"),
            },
            clear=False,
        ):
            result = run_doctor_checks()

    warns = [c for c in result.checks if c.level == DoctorLevel.WARN]
    assert all("Dummy Profile" not in c.name for c in warns), [c.name for c in warns]
    assert all(
        c.name in {"Temporary Directory", "Swap", "Compressed Swap", "Shell History"}
        for c in warns
    ), [c.name for c in warns]
