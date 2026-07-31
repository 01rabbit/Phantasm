"""What the free-space filler is allowed to put in a Face.

`docs/CLAIMS.md` CLM-40 says the filler "does not forge forensic artifacts,
fake kernel logs, or perform timestamp forgery". Until this module existed, the
evidence cited for that claim was `tests/test_dummy_generator.py` — tests of
`src/phasmid/dummy_generator.py`, a module **no operator could reach**: nothing
in `src/` imported it, and no CLI subcommand, TUI action or WebUI endpoint
called it. The claim was about the shipped behaviour and the evidence was about
something else (#165).

The filler that ships is `VesselWorkflowService._build_generated_file_specs`,
reached through `generate_dummy_profile`. These tests hold it to the claim.

The distinction the claim rests on: filler exists so a container does not read
as suspiciously empty. It is **not** disclosure material — that is the
operator's to prepare — and it must not read as evidence of anything. A
generated file that looked like a system log or a forensic artifact would be
the tool manufacturing a cover story, which is the position this project
explicitly abandoned.
"""

from __future__ import annotations

import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))

from phasmid.services.vessel_workflow_service import VesselWorkflowService

#: Substrings that would make a generated file read as a system or forensic
#: record rather than as ordinary working material.
FORGED_ARTEFACT_MARKERS = (
    "kernel:",
    "syslog",
    "dmesg",
    "systemd[",
    "audit(",
    "/var/log",
    "segfault",
    "Call Trace:",
    "sshd[",
    "sudo:",
    "pam_unix",
    "iptables",
    "SHA256:",
    "BEGIN CERTIFICATE",
    "BEGIN RSA PRIVATE KEY",
)


class FillerContentTests(unittest.TestCase):
    def setUp(self):
        self.specs = VesselWorkflowService()._build_generated_file_specs(64 * 1024)
        self.assertTrue(self.specs, "the filler produced nothing to inspect")

    def _all_text(self) -> str:
        return "\n".join(
            payload.decode("utf-8", errors="ignore") for _name, payload in self.specs
        )

    def test_no_generated_file_reads_as_a_system_log_or_forensic_artefact(self):
        """CLM-40, against the code that ships."""
        haystack = self._all_text()
        for marker in FORGED_ARTEFACT_MARKERS:
            with self.subTest(marker=marker):
                self.assertNotIn(marker, haystack)

    def test_no_generated_file_carries_a_fabricated_timestamp(self):
        """Timestamp forgery, stated as what it would look like.

        Filler is written into the Face namespace, which stamps `added_at` with
        the real time of writing. Nothing in the payloads should assert a date
        of its own - a file that claims to be from last March is the tool
        inventing a history.
        """
        dated = re.compile(
            r"\d{4}-\d{2}-\d{2}"  # ISO date
            r"|\d{1,2}/\d{1,2}/\d{2,4}"  # slashed date
            r"|(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}\s"
        )
        for name, payload in self.specs:
            with self.subTest(name=name):
                found = dated.search(payload.decode("utf-8", errors="ignore"))
                self.assertIsNone(
                    found,
                    f"{name} carries what reads as a date: {found and found.group(0)!r}",
                )

    def test_the_filler_is_deterministic(self):
        """No weak randomness, and nothing that varies run to run.

        Inherited from a test of the unreachable module, which asserted the
        same property by reading its source for `random.*`. Asserted here on
        behaviour instead: two runs at the same size produce the same bytes.
        """
        again = VesselWorkflowService()._build_generated_file_specs(64 * 1024)
        self.assertEqual(self.specs, again)

    def test_the_names_do_not_claim_provenance(self):
        """A filename is the first thing read, and can imply an origin by itself."""
        for name, _payload in self.specs:
            with self.subTest(name=name):
                lowered = name.lower()
                for claim in ("evidence", "backup", "export", "dump", "log_"):
                    self.assertNotIn(claim, lowered)

    def test_an_empty_target_produces_nothing(self):
        self.assertEqual(VesselWorkflowService()._build_generated_file_specs(0), [])
        self.assertEqual(VesselWorkflowService()._build_generated_file_specs(-1), [])


if __name__ == "__main__":
    unittest.main()
