"""A password that ends an entry, entered where a password that opens one goes.

The point of this path is that nothing distinguishes it. Same screen, same
field, same button, same response - only the password differs. That is the
answer to "they will just make you type the password": the password they can
compel is not the only one there is.

It has to hold in both directions, and each of these is a way it could be got
wrong:

- an access password must still open, so the destroy check can never shadow it;
- the destroy password must leave *no* visible trace, or the path is pointless;
- it is scoped to the entry whose object is present, so one entry's destroy
  password can never reach the other;
- the entry it clears really is cleared, and the other one really does survive.
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))

from phasmid import strings as text
from phasmid import web_server
from phasmid.services.vessel_workflow_service import VesselWorkflowService

ACCESS_ONE = "access-one"
DESTROY_ONE = "clear-one"
ACCESS_TWO = "access-two"


class DestroyByPasswordTests(unittest.TestCase):
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

        self.cue = web_server.access_cue_service
        self.modes = self.cue.modes()
        self.service = VesselWorkflowService()
        self.vessel = Path(self._dirs.name) / "demo.vessel"
        self.service.create_vessel(self.vessel, "8M")
        # Stored the way the WebUI stores: no object arguments, so the binding
        # lives in the cue store rather than the registry.
        self.service.add_payload(
            self.vessel,
            "one.txt",
            b"the contents of entry one",
            ACCESS_ONE,
            restricted_passphrase=DESTROY_ONE,
            selector="face_a",
            cue_sequence=self.cue.sequence_for_mode(self.modes[0]),
        )
        self.service.add_payload(
            self.vessel,
            "two.txt",
            b"the contents of entry two",
            ACCESS_TWO,
            selector="face_b",
            cue_sequence=self.cue.sequence_for_mode(self.modes[1]),
        )

    def tearDown(self):
        web_server._rate_limit.clear()
        web_server._access_attempts._state.clear()

    def _attempt(self, mode, password):
        """One POST /retrieve with *mode*'s object in front of the camera."""

        async def run():
            request = SimpleNamespace(
                client=SimpleNamespace(host="127.0.0.1"),
                url=SimpleNamespace(path="/retrieve"),
                cookies={},
            )
            with (
                mock.patch.object(
                    self.cue,
                    "auth_sequence",
                    return_value=list(self.cue.sequence_for_mode(mode, length=1)),
                ),
                mock.patch.object(
                    web_server, "_raw_gate_status", return_value={"matched_mode": mode}
                ),
                mock.patch.object(
                    web_server, "resolve_web_vessel", return_value=str(self.vessel)
                ),
            ):
                return await web_server.retrieve(request, password=password)

        response = asyncio.run(run())
        web_server._rate_limit.clear()
        web_server._access_attempts._state.clear()
        return response

    def _opens(self, mode, password) -> bool:
        return not isinstance(self._attempt(mode, password), dict)

    def test_an_access_password_still_opens_its_entry(self):
        """The destroy check runs after retrieval, so it can never shadow this."""
        self.assertTrue(self._opens(self.modes[0], ACCESS_ONE))
        self.assertTrue(self._opens(self.modes[1], ACCESS_TWO))

    def test_the_destroy_password_clears_the_entry_it_belongs_to(self):
        self.assertTrue(self._opens(self.modes[0], ACCESS_ONE))
        self._attempt(self.modes[0], DESTROY_ONE)
        self.assertFalse(
            self._opens(self.modes[0], ACCESS_ONE),
            "the entry opened again after its destroy password was used",
        )

    def test_the_other_entry_survives(self):
        """Show one, end the other - the whole reason this exists."""
        self._attempt(self.modes[0], DESTROY_ONE)
        self.assertTrue(
            self._opens(self.modes[1], ACCESS_TWO),
            "clearing one entry took the other with it",
        )

    def test_it_looks_exactly_like_a_mistyped_password(self):
        """Anything visible here would defeat the point of the path."""
        destroyed = self._attempt(self.modes[0], DESTROY_ONE)
        mistyped = self._attempt(self.modes[1], "not the password at all")
        self.assertEqual(destroyed, mistyped)
        self.assertEqual(destroyed, {"error": text.NO_VALID_ENTRY_FOUND})

    def test_one_entrys_destroy_password_cannot_reach_the_other(self):
        """Scoped by the object presented, not by the password alone."""
        self._attempt(self.modes[1], DESTROY_ONE)
        self.assertTrue(
            self._opens(self.modes[1], ACCESS_TWO),
            "the wrong entry was cleared",
        )
        self.assertTrue(
            self._opens(self.modes[0], ACCESS_ONE),
            "the entry that owns the password was cleared without its object",
        )

    def test_it_does_not_fire_without_an_object(self):
        async def run():
            request = SimpleNamespace(
                client=SimpleNamespace(host="127.0.0.1"),
                url=SimpleNamespace(path="/retrieve"),
                cookies={},
            )
            with (
                mock.patch.object(
                    self.cue, "auth_sequence", return_value=[self.cue.match_none()]
                ),
                mock.patch.object(web_server, "_raw_gate_status", return_value={}),
                mock.patch.object(
                    web_server, "resolve_web_vessel", return_value=str(self.vessel)
                ),
            ):
                return await web_server.retrieve(request, password=DESTROY_ONE)

        self.assertEqual(asyncio.run(run()), {"error": text.NO_VALID_ENTRY_FOUND})
        web_server._rate_limit.clear()
        web_server._access_attempts._state.clear()
        self.assertTrue(self._opens(self.modes[0], ACCESS_ONE))

    def test_using_it_does_not_count_against_the_lockout(self):
        """An operator who has just cleared one entry still has to open another.

        The credential was correct, so charging it as a failure would spend the
        attempts they need next - at the worst possible moment.
        """
        request = SimpleNamespace(
            client=SimpleNamespace(host="127.0.0.1"),
            url=SimpleNamespace(path="/retrieve"),
            cookies={},
        )
        scope = f"web:{web_server._client_id(request)}"

        async def run():
            with (
                mock.patch.object(
                    self.cue,
                    "auth_sequence",
                    return_value=list(
                        self.cue.sequence_for_mode(self.modes[0], length=1)
                    ),
                ),
                mock.patch.object(
                    web_server,
                    "_raw_gate_status",
                    return_value={"matched_mode": self.modes[0]},
                ),
                mock.patch.object(
                    web_server, "resolve_web_vessel", return_value=str(self.vessel)
                ),
            ):
                return await web_server.retrieve(request, password=DESTROY_ONE)

        for _ in range(4):
            web_server._access_attempts.record_failure(scope)
        asyncio.run(run())
        self.assertTrue(
            web_server._access_attempts.check(scope).allowed,
            "clearing an entry spent the attempts needed to open the other one",
        )


if __name__ == "__main__":
    unittest.main()
