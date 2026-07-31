"""Nothing that needs the object may ask while nothing is looking.

A successful retrieval calls `access_cue_service.close()` to save power and
heat. That stops the background matcher, so every later "is the bound object
present?" is answered *no* - not because the object is absent, but because
nothing is watching for it. The retrieve page brings it back on its next
`/video_feed` request, which made the answer depend on whether the browser had
reconnected its preview yet.

Reported from the device as the explicit clear panel refusing an object that
was plainly in front of the camera, right after a successful retrieval.
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))

from phasmid import strings as text
from phasmid import web_server


def _request(path):
    return SimpleNamespace(
        client=SimpleNamespace(host="127.0.0.1"),
        url=SimpleNamespace(path=path),
        cookies={},
    )


class ResumeCueMatchingTests(unittest.TestCase):
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

    def tearDown(self):
        web_server._rate_limit.clear()
        web_server._access_attempts._state.clear()

    def _matcher(self, running: bool):
        return mock.patch.object(
            type(web_server.access_cue_service),
            "matching_active",
            property(lambda self: running),
        )

    def test_a_stopped_matcher_is_restarted(self):
        with (
            self._matcher(False),
            mock.patch.object(web_server.access_cue_service, "start") as start,
            mock.patch.object(web_server, "VesselWorkflowService") as svc,
        ):
            svc.return_value.wait_for_camera_frame.return_value = True
            web_server._resume_cue_matching()
        start.assert_called_once()
        svc.return_value.wait_for_reference_match.assert_called_once()

    def test_a_running_matcher_is_left_alone(self):
        """The normal case has to stay free - this runs on every retrieval."""
        with (
            self._matcher(True),
            mock.patch.object(web_server.access_cue_service, "start") as start,
            mock.patch.object(web_server, "VesselWorkflowService") as svc,
        ):
            web_server._resume_cue_matching()
        start.assert_not_called()
        svc.assert_not_called()

    def test_a_device_with_no_camera_does_not_stand_and_wait(self):
        """Otherwise every call on a camera-less host pays the settle time."""
        with (
            self._matcher(False),
            mock.patch.object(web_server.access_cue_service, "start"),
            mock.patch.object(web_server, "VesselWorkflowService") as svc,
        ):
            svc.return_value.wait_for_camera_frame.return_value = False
            web_server._resume_cue_matching()
        svc.return_value.wait_for_reference_match.assert_not_called()

    def test_a_failure_to_resume_does_not_break_the_request(self):
        """It is best-effort - but it says so in the log, or nobody can tell."""
        with (
            self._matcher(False),
            mock.patch.object(web_server.access_cue_service, "start", side_effect=None),
            mock.patch.object(
                web_server,
                "VesselWorkflowService",
                side_effect=RuntimeError("no camera"),
            ),
        ):
            with self.assertLogs("phasmid.web_server", level="ERROR"):
                web_server._resume_cue_matching()  # must not raise

    def test_clearing_an_entry_resumes_the_matcher_first(self):
        """The reported failure: the panel refused an object that was there."""

        async def run():
            with (
                self._matcher(False),
                mock.patch.object(web_server, "_resume_cue_matching") as resume,
                mock.patch.object(
                    web_server.access_cue_service,
                    "auth_sequence",
                    return_value=[web_server.access_cue_service.match_none()],
                ),
                mock.patch.object(web_server, "_raw_gate_status", return_value={}),
            ):
                response = await web_server.destroy_face(
                    _request("/destroy_face"), password="x", confirmation="DESTROY FACE"
                )
            resume.assert_called_once()
            self.assertEqual(response["error"], text.DESTROY_FACE_NO_OBJECT)

        asyncio.run(run())

    def test_retrieving_resumes_the_matcher_first(self):
        async def run():
            with (
                self._matcher(False),
                mock.patch.object(web_server, "_resume_cue_matching") as resume,
                mock.patch.object(
                    web_server.access_cue_service,
                    "auth_sequence",
                    return_value=[web_server.access_cue_service.match_none()],
                ),
            ):
                await web_server.retrieve(_request("/retrieve"), password="x")
            resume.assert_called_once()

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
