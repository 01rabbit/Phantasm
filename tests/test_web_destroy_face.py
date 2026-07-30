"""Clearing a protected entry from the WebUI.

The destroy credential existed only in `phasmid emergency destroy-face`, so the
one scenario the tool exists for - refusing to disclose under duress - was the
one that dropped out of the browser and onto a terminal. `/destroy_face` closes
that, reusing the service call the CLI already uses.

Three things have to hold, and each is a way this could be got wrong:

- the entry cleared is chosen by the *object in front of the camera*, never by a
  form field, because naming an entry on screen says there is more than one;
- the destroy password is a distinct credential from the access password, so a
  coerced operator handing over the access password has not handed over this;
- every refusal reads the same, so which of the two entries the caller can reach
  is not disclosed by the difference between "wrong password" and "no entry".
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from fastapi import HTTPException

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))

from phasmid import strings as text
from phasmid import web_server
from phasmid.restricted_actions import DESTROY_FACE_PHRASE
from phasmid.services.vessel_workflow_service import VesselWorkflowService


def _request():
    """A caller with no restricted-confirmation session.

    Deliberately cookie-less: the `destroy_face` policy does not require one,
    because unlike the other restricted actions this is gated by a credential.
    A test that handed it a valid session would stop noticing if that changed.
    """
    return SimpleNamespace(
        client=SimpleNamespace(host="127.0.0.1"),
        url=SimpleNamespace(path="/destroy_face"),
        cookies={},
    )


class DestroyFaceTests(unittest.TestCase):
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
        self.matched_mode = web_server.access_cue_service.modes()[1]

    def tearDown(self):
        web_server._rate_limit.clear()
        web_server._access_attempts._state.clear()

    def _with_object_present(self):
        """The camera sees the object bound to the second entry."""
        return (
            mock.patch.object(
                web_server.access_cue_service,
                "auth_sequence",
                return_value=[self.matched_mode],
            ),
            mock.patch.object(
                web_server,
                "_raw_gate_status",
                return_value={"matched_mode": self.matched_mode},
            ),
        )

    def _with_no_object(self):
        return (
            mock.patch.object(
                web_server.access_cue_service,
                "auth_sequence",
                return_value=[web_server.access_cue_service.match_none()],
            ),
            mock.patch.object(web_server, "_raw_gate_status", return_value={}),
        )

    def test_it_clears_the_entry_whose_object_is_presented(self):
        async def run():
            present_a, present_b = self._with_object_present()
            with (
                present_a,
                present_b,
                mock.patch.object(
                    web_server, "resolve_web_vessel", return_value="/tmp/demo.vessel"
                ),
                mock.patch.object(
                    web_server, "VesselWorkflowService"
                ) as service_factory,
            ):
                response = await web_server.destroy_face(
                    _request(),
                    password="destroy-me",
                    confirmation=DESTROY_FACE_PHRASE,
                )
            call = service_factory.return_value.destroy_face.call_args
            # Asserted through the workflow service's own resolution rather
            # than on the raw selector string: what matters is *which Face*
            # this clears, not which of the two equivalent vocabularies the
            # handler happens to speak.
            self.assertEqual(
                VesselWorkflowService().resolve_face_id(call.kwargs["selector"]),
                "face_b",
            )
            self.assertEqual(call.args[1], "destroy-me")
            self.assertTrue(call.kwargs["camera_object"])
            self.assertEqual(response["status"], text.DESTROY_FACE_DONE)

        asyncio.run(run())

    def test_without_the_object_it_refuses_and_says_so(self):
        """Actionable: it describes the frame, not anything stored."""

        async def run():
            absent_a, absent_b = self._with_no_object()
            with (
                absent_a,
                absent_b,
                mock.patch.object(
                    web_server, "VesselWorkflowService"
                ) as service_factory,
            ):
                response = await web_server.destroy_face(
                    _request(),
                    password="destroy-me",
                    confirmation=DESTROY_FACE_PHRASE,
                )
            service_factory.return_value.destroy_face.assert_not_called()
            self.assertEqual(response["error"], text.DESTROY_FACE_NO_OBJECT)

        asyncio.run(run())

    def test_the_object_is_checked_before_the_confirmation_phrase(self):
        """Otherwise a mistyped phrase would be reported to someone holding nothing.

        Order matters for what leaks: the phrase check raises a 403 naming a
        rejected confirmation, which tells a caller the request got past the
        camera. It must not.
        """

        async def run():
            absent_a, absent_b = self._with_no_object()
            with absent_a, absent_b:
                response = await web_server.destroy_face(
                    _request(), password="x", confirmation="nope"
                )
            self.assertEqual(response["error"], text.DESTROY_FACE_NO_OBJECT)

        asyncio.run(run())

    def test_a_wrong_confirmation_phrase_stops_it(self):
        async def run():
            present_a, present_b = self._with_object_present()
            with (
                present_a,
                present_b,
                mock.patch.object(
                    web_server, "VesselWorkflowService"
                ) as service_factory,
            ):
                with self.assertRaises(HTTPException) as ctx:
                    await web_server.destroy_face(
                        _request(),
                        password="destroy-me",
                        confirmation="DESTROY",
                    )
            service_factory.return_value.destroy_face.assert_not_called()
            self.assertEqual(ctx.exception.detail, text.CONFIRMATION_REJECTED)

        asyncio.run(run())

    def test_a_wrong_destroy_password_reads_like_every_other_refusal(self):
        async def run():
            present_a, present_b = self._with_object_present()
            service = mock.Mock()
            service.destroy_face.side_effect = ValueError("emergency password mismatch")
            with (
                present_a,
                present_b,
                mock.patch.object(
                    web_server, "resolve_web_vessel", return_value="/tmp/demo.vessel"
                ),
                mock.patch.object(
                    web_server, "VesselWorkflowService", return_value=service
                ),
            ):
                response = await web_server.destroy_face(
                    _request(),
                    password="wrong",
                    confirmation=DESTROY_FACE_PHRASE,
                )
            self.assertEqual(response["error"], text.OPERATION_REJECTED)
            self.assertNotIn("password", response["error"].lower())

        asyncio.run(run())

    def test_repeated_wrong_passwords_hit_the_lockout(self):
        """A destroy password must not be more brute-forceable than an access one."""

        async def run():
            present_a, present_b = self._with_object_present()
            service = mock.Mock()
            service.destroy_face.side_effect = ValueError("emergency password mismatch")
            with (
                present_a,
                present_b,
                mock.patch.object(
                    web_server, "resolve_web_vessel", return_value="/tmp/demo.vessel"
                ),
                mock.patch.object(
                    web_server, "VesselWorkflowService", return_value=service
                ),
            ):
                for _ in range(6):
                    response = await web_server.destroy_face(
                        _request(),
                        password="wrong",
                        confirmation=DESTROY_FACE_PHRASE,
                    )
            self.assertEqual(response["error"], text.ACCESS_TEMPORARILY_UNAVAILABLE)

        asyncio.run(run())

    def test_it_passes_the_phrase_the_cli_uses(self):
        """The two interfaces ask for the same words, not two dialects."""
        self.assertEqual(DESTROY_FACE_PHRASE, "DESTROY FACE")

        async def run():
            present_a, present_b = self._with_object_present()
            with (
                present_a,
                present_b,
                mock.patch.object(
                    web_server, "resolve_web_vessel", return_value="/tmp/demo.vessel"
                ),
                mock.patch.object(
                    web_server, "VesselWorkflowService"
                ) as service_factory,
            ):
                await web_server.destroy_face(
                    _request(),
                    password="destroy-me",
                    confirmation=DESTROY_FACE_PHRASE,
                )
            call = service_factory.return_value.destroy_face.call_args
            self.assertEqual(call.kwargs["confirmation"], DESTROY_FACE_PHRASE)

        asyncio.run(run())


class DestroyFaceSurfaceTests(unittest.TestCase):
    """The page has to offer it, and has to say which password it wants."""

    def _retrieve_template(self) -> str:
        path = os.path.join(ROOT, "src", "phasmid", "templates", "retrieve.html")
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()

    def test_the_retrieve_page_offers_the_destroy_path(self):
        page = self._retrieve_template()
        self.assertIn("/destroy_face", page)
        self.assertIn("destroy_face_phrase", page)

    def test_the_page_distinguishes_the_two_passwords(self):
        """Handing over the access password must not read as handing over this."""
        page = self._retrieve_template()
        self.assertIn("Clearing password", page)
        self.assertIn("Its access password will not do this", page)

    def test_the_page_does_not_let_the_caller_name_the_entry(self):
        """A selector here would put "there are two of them" on screen."""
        page = self._retrieve_template()
        destroy_form = page.split('id="destroyForm"')[1].split("</form>")[0]
        self.assertNotIn("<select", destroy_form)
        self.assertNotIn("entry_1", destroy_form)
        self.assertNotIn("entry_2", destroy_form)


if __name__ == "__main__":
    unittest.main()
