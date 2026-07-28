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


def test_doctor_does_not_report_a_filler_profile_it_cannot_measure():
    """Four checks used to read a path nothing writes.

    Every reference to `.state/dummy_profile` in the tree is a reader; the
    one module that could populate it has no operator-reachable entry point,
    and the operator-facing feature writes into the Vessel's face namespace
    instead. So those checks could not pass on any device, and they
    contradicted the Audit screen, which reads the Vessel and is correct.

    Free-space filler is per-Vessel and per-face. This is a host check with
    no Vessel context, so it must not claim to report one.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        with mock.patch.dict(os.environ, {"PHASMID_STATE_DIR": tmpdir}, clear=False):
            result = run_doctor_checks()

    names = [check.name for check in result.checks]
    for gone in (
        "Dummy Profile Size",
        "Dummy Profile File Count",
        "Dummy Profile Occupancy Ratio",
        "Dummy Profile Size Distribution",
        "Dummy Profile Plausibility",
    ):
        assert gone not in names, f"{gone} reports a path no operation writes"

    assert "Free Space Reporting" in names
    pointer = next(c for c in result.checks if c.name == "Free Space Reporting")
    assert pointer.level == DoctorLevel.INFO


def test_a_fresh_host_warns_only_about_genuine_host_facts():
    """The warning count is a talking point, so it has to be honest.

    Four of the five warnings on a fresh device came from the dead path
    above and could never clear. What is left describes the machine.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        with mock.patch.dict(os.environ, {"PHASMID_STATE_DIR": tmpdir}, clear=False):
            result = run_doctor_checks()

    warns = [c for c in result.checks if c.level == DoctorLevel.WARN]
    assert all("Dummy Profile" not in c.name for c in warns), [c.name for c in warns]
    # Swap and zram are real facts about the host and appear on the Pi; a
    # world-writable /tmp is the one this container reproduces.
    assert all(
        c.name in {"Temporary Directory", "Swap", "Compressed Swap", "Shell History"}
        for c in warns
    ), [c.name for c in warns]
