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
from pathlib import Path
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


class DestroyFaceAgainstWebStoredDataTests(unittest.TestCase):
    """The service call has to accept what the WebUI actually writes.

    A Face can be bound two ways. The CLI records a perceptual fingerprint in
    the registry (`object_binding`); the WebUI binds through the ORB cue store
    and writes no registry record at all. `destroy_face` asked only the
    registry, so it raised "object binding not registered" for every Face the
    WebUI had ever protected - and `/destroy_face` reported that as an ordinary
    rejection, indistinguishable from a wrong destroy password. Measured on a
    WebUI-stored Face: the destroy password verified, and the call still failed.
    """

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
        self.modes = web_server.access_cue_service.modes()
        # Exactly the call the /store handler makes: no object arguments, so no
        # registry binding record is ever written.
        self.service.add_payload(
            self.vessel,
            "real.txt",
            b"the real thing",
            "access-pw",
            restricted_passphrase="destroy-pw",
            selector="face_a",
            cue_sequence=web_server.access_cue_service.sequence_for_mode(self.modes[0]),
        )
        self.service.add_payload(
            self.vessel,
            "decoy.txt",
            b"the decoy",
            "other-pw",
            selector="face_b",
            cue_sequence=web_server.access_cue_service.sequence_for_mode(self.modes[1]),
        )

    def _showing(self, mode):
        return mock.patch.object(
            web_server.access_cue_service,
            "auth_sequence",
            return_value=list(
                web_server.access_cue_service.sequence_for_mode(mode, length=1)
            ),
        )

    def _opens(self, selector, password, mode) -> bool:
        try:
            self.service.retrieve_payload(
                self.vessel,
                password,
                selector=selector,
                cue_sequence=list(
                    web_server.access_cue_service.sequence_for_mode(mode, length=1)
                ),
            )
        except (ValueError, FileNotFoundError, PermissionError, RuntimeError):
            return False
        return True

    def test_the_web_stored_face_writes_no_registry_binding(self):
        """States the premise the rest of this class depends on."""
        record = self.service._get_face_binding_record(self.vessel, "face_a")
        self.assertFalse(self.service._binding_registered(record))

    def test_the_right_object_and_destroy_password_clear_it(self):
        with self._showing(self.modes[0]):
            result = self.service.destroy_face(
                self.vessel,
                "destroy-pw",
                selector="face_a",
                camera_object=True,
                confirmation=DESTROY_FACE_PHRASE,
            )
        self.assertEqual(result.face_id, "face_a")

    def test_the_other_face_survives_and_still_opens(self):
        """The whole point: show one, protect the other."""
        with self._showing(self.modes[0]):
            self.service.destroy_face(
                self.vessel,
                "destroy-pw",
                selector="face_a",
                camera_object=True,
                confirmation=DESTROY_FACE_PHRASE,
            )
        self.assertTrue(self._opens("face_b", "other-pw", self.modes[1]))
        self.assertFalse(self._opens("face_a", "access-pw", self.modes[0]))

    def test_it_still_refuses_without_the_right_object_or_password(self):
        cases = (
            (
                "no object at all",
                [web_server.access_cue_service.match_none()],
                "destroy-pw",
            ),
            (
                "the other Face's object",
                list(web_server.access_cue_service.sequence_for_mode(self.modes[1])),
                "destroy-pw",
            ),
            (
                "right object, wrong destroy password",
                list(web_server.access_cue_service.sequence_for_mode(self.modes[0])),
                "not-the-password",
            ),
        )
        for label, sequence, password in cases:
            with self.subTest(case=label):
                with mock.patch.object(
                    web_server.access_cue_service,
                    "auth_sequence",
                    return_value=sequence,
                ):
                    with self.assertRaises(ValueError):
                        self.service.destroy_face(
                            self.vessel,
                            password,
                            selector="face_a",
                            camera_object=True,
                            confirmation=DESTROY_FACE_PHRASE,
                        )
                self.assertTrue(self._opens("face_a", "access-pw", self.modes[0]))


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
