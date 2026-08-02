"""The interface has to answer while the device is busy.

Reported from the device, in the middle of the demonstration sequence: clear an
entry with its destroy password, confirm its access password no longer opens
it, press Home - and the interface never comes back.

Nothing was wrong with Home. Every route in `web_server` was written
`async def`, which in FastAPI means the body runs on the one event loop, and
the bodies that matter here are not asynchronous at all. They derive keys with
Argon2id, overwrite container bytes, and poll the camera with `time.sleep`. On
a Pi Zero 2 W that is seconds per request, and for all of it uvicorn can serve
nothing else.

The second step of that sequence is the most expensive path in the whole
application: every mode's Argon2id runs and fails against bytes that are now
random, and only then does the destroy-password check run its own. Nothing
short-circuits, so the stall is as long as it can be exactly when the operator
is standing on stage.

These tests hold the two halves of the fix in place - the work runs off the
loop, and it still cannot overlap with itself.
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))

from phasmid import web_server  # noqa: E402

#: Long enough to be unmistakable against the loop's own scheduling on a
#: contended CI runner, short enough that the suite does not notice. The
#: assertion below is "the loop was alive", not "the loop was fast", so the
#: margin between this and the tick is deliberately wide: a tight one turns a
#: real regression test into a flake, and a flaky test gets muted.
BLOCK_SECONDS = 1.0

#: What the loop is asked to do while the block is in flight - the home page's
#: stand-in. Overshooting this by several multiples still passes.
LOOP_TICK_SECONDS = 0.05

#: The loop must have come back well before the blocking call finished. Half
#: the block is already generous: on the loop it could not have come back at
#: all until the full second was over.
LOOP_MUST_RESPOND_WITHIN = BLOCK_SECONDS / 2


def _request():
    return SimpleNamespace(
        client=SimpleNamespace(host="127.0.0.1"),
        url=SimpleNamespace(path="/retrieve"),
        cookies={},
    )


class TheLoopKeepsTurningTests(unittest.IsolatedAsyncioTestCase):
    async def test_a_blocking_retrieval_does_not_stop_the_event_loop(self):
        """The reported failure, reduced to its mechanism.

        `time.sleep` inside an `async def` body stops every other request on
        the process. The probe below is the home page's stand-in: if it cannot
        run while a retrieval is in flight, neither could Home.
        """
        original = web_server._retrieve
        web_server._retrieve = lambda *a, **k: (time.sleep(BLOCK_SECONDS), {})[1]
        self.addCleanup(setattr, web_server, "_retrieve", original)

        started = time.perf_counter()
        task = asyncio.create_task(web_server.retrieve(_request(), password="x"))
        await asyncio.sleep(LOOP_TICK_SECONDS)
        loop_responded_after = time.perf_counter() - started
        await task
        blocked_for = time.perf_counter() - started

        self.assertGreaterEqual(blocked_for, BLOCK_SECONDS)
        self.assertLess(loop_responded_after, LOOP_MUST_RESPOND_WITHIN)

    async def test_every_route_that_can_block_is_off_the_loop(self):
        """Named individually, because each one was found by reading it.

        A route added here later without an implementation half will fail this
        rather than fail on stage.
        """
        for name in (
            "retrieve",
            "destroy_face",
            "purge_other",
            "store",
            "register_key",
            "register_scene",
            "emergency_brick",
            "emergency_initialize",
            "web_panic_trigger",
        ):
            with self.subTest(route=name):
                self.assertTrue(
                    hasattr(web_server, f"_{name}"),
                    f"{name} has no synchronous implementation to offload to",
                )


class OneAtATimeTests(unittest.IsolatedAsyncioTestCase):
    """What the event loop used to guarantee for free.

    While every body ran on the loop, two container operations could not
    overlap. Moving them to the threadpool takes that away unless something
    puts it back, and a second retrieval landing in the middle of a purge is
    not a race worth discovering on a device.
    """

    async def test_two_container_operations_do_not_overlap(self):
        concurrent = 0
        peak = 0
        seen = threading.Lock()

        def busy(*_args, **_kwargs):
            nonlocal concurrent, peak
            with seen:
                concurrent += 1
                peak = max(peak, concurrent)
            time.sleep(0.15)
            with seen:
                concurrent -= 1
            return {}

        original = web_server._retrieve
        web_server._retrieve = busy
        self.addCleanup(setattr, web_server, "_retrieve", original)

        await asyncio.gather(
            web_server.retrieve(_request(), password="a"),
            web_server.retrieve(_request(), password="b"),
            web_server.retrieve(_request(), password="c"),
        )
        self.assertEqual(peak, 1)

    async def test_the_lock_is_released_when_the_body_raises(self):
        """Otherwise the first unexpected fault takes the interface with it."""

        def explode(*_args, **_kwargs):
            raise RuntimeError("container gone")

        original = web_server._retrieve
        web_server._retrieve = explode
        self.addCleanup(setattr, web_server, "_retrieve", original)

        with self.assertRaises(RuntimeError):
            await web_server.retrieve(_request(), password="x")
        self.assertFalse(web_server._DEVICE_OPERATION_LOCK.locked())


class TheStatusPollerTests(unittest.TestCase):
    """The other half of the hang, and the half that made it permanent.

    A stalled server is recoverable; a browser with no sockets left is not.
    The camera preview holds one MJPEG connection for the life of the page, and
    a poller that fires every 1.2 s without waiting for the previous reply
    consumes the rest within seconds. The navigation that follows then never
    leaves the browser - which is what "the WebUI froze" looked like, with a
    perfectly healthy server behind it.
    """

    def setUp(self):
        self.script = Path(ROOT, "src", "phasmid", "templates", "base.html").read_text(
            encoding="utf-8"
        )
        match = re.search(
            r"async function pollStatus\(\) \{(.*?)\n        \}", self.script, re.S
        )
        self.assertIsNotNone(match, "pollStatus is no longer where this test looks")
        self.body = match.group(1)

    def test_a_poll_does_not_start_while_one_is_outstanding(self):
        self.assertIn("if (statusInFlight) return;", self.body)

    def test_the_flag_is_cleared_however_the_poll_ends(self):
        """A poll that throws must not wedge the poller closed forever."""
        self.assertIn("finally", self.body)
        self.assertRegex(self.body, r"finally \{[^}]*statusInFlight = false;")

    def test_a_poll_cannot_hang_indefinitely(self):
        """An abandoned request holds its socket for as long as it lives."""
        self.assertIn("AbortController", self.body)
        self.assertIn("signal: abort.signal", self.body)
        self.assertIn("STATUS_TIMEOUT_MS", self.script)

    def test_the_timeout_is_shorter_than_the_operations_it_waits_behind(self):
        """Otherwise it is not a timeout, it is the same stall with a name."""
        timeout = int(re.search(r"STATUS_TIMEOUT_MS = (\d+)", self.script).group(1))
        self.assertLessEqual(timeout, 5000)


if __name__ == "__main__":
    unittest.main()
