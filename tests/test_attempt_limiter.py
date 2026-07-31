import os
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(__file__))
import sys

sys.path.insert(0, os.path.join(ROOT, "src"))

from phasmid.attempt_limiter import AttemptLimiter, FileAttemptLimiter
from phasmid.state_store import LocalStateStore


class AttemptLimiterTests(unittest.TestCase):
    def test_repeated_failures_trigger_lockout(self):
        now = [1000]
        limiter = AttemptLimiter(
            max_failures=2,
            lockout_seconds=30,
            clock=lambda: now[0],
        )

        self.assertTrue(limiter.check("local").allowed)
        limiter.record_failure("local")
        self.assertTrue(limiter.check("local").allowed)
        limiter.record_failure("local")

        decision = limiter.check("local")
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.wait_seconds, 30)

    def test_success_resets_attempt_state(self):
        limiter = AttemptLimiter(max_failures=1, lockout_seconds=30, clock=lambda: 1000)

        limiter.record_failure("local")
        self.assertFalse(limiter.check("local").allowed)
        limiter.record_success("local")

        self.assertTrue(limiter.check("local").allowed)

    def test_serving_the_lockout_clears_the_failures_that_earned_it(self):
        """Otherwise the penalty never ends.

        The count used to survive its own lockout, so after waiting the full
        period the caller still stood at max_failures and the next single
        mistake locked them out again - indefinitely, unless they could produce
        a success. Reported from the device as the lockout "dragging on" long
        after its sixty seconds were up.
        """
        now = [1000]
        limiter = AttemptLimiter(
            max_failures=2, lockout_seconds=30, clock=lambda: now[0]
        )
        limiter.record_failure("local")
        limiter.record_failure("local")
        self.assertFalse(limiter.check("local").allowed)

        now[0] += 31
        self.assertTrue(limiter.check("local").allowed, "the lockout never expired")

        # The first mistake after waiting is a first mistake, not a sixth.
        limiter.record_failure("local")
        self.assertTrue(
            limiter.check("local").allowed,
            "one failure after serving the lockout locked the caller out again",
        )

    def test_the_lockout_still_holds_for_its_full_period(self):
        """A fix that forgot too eagerly would pass the test above for free."""
        now = [1000]
        limiter = AttemptLimiter(
            max_failures=2, lockout_seconds=30, clock=lambda: now[0]
        )
        limiter.record_failure("local")
        limiter.record_failure("local")
        for elapsed in (0, 15, 29):
            now[0] = 1000 + elapsed
            with self.subTest(elapsed=elapsed):
                self.assertFalse(limiter.check("local").allowed)

    def test_checking_during_the_lockout_does_not_extend_it(self):
        now = [1000]
        limiter = AttemptLimiter(
            max_failures=2, lockout_seconds=30, clock=lambda: now[0]
        )
        limiter.record_failure("local")
        limiter.record_failure("local")
        for _ in range(10):
            limiter.check("local")
        now[0] += 31
        self.assertTrue(limiter.check("local").allowed)

    def test_the_file_limiter_forgets_an_expired_lockout_across_restarts(self):
        tmpdir = tempfile.mkdtemp()
        store = LocalStateStore(tmpdir)
        now = [1000]

        def limiter():
            return FileAttemptLimiter(
                store=store, max_failures=1, lockout_seconds=30, clock=lambda: now[0]
            )

        first = limiter()
        first.record_failure("cli")
        self.assertFalse(first.check("cli").allowed)

        now[0] += 31
        self.assertTrue(first.check("cli").allowed)

        # The clearing has to reach disk, or a restart resurrects the count.
        self.assertTrue(limiter().check("cli").allowed)

    def test_the_file_limiter_can_record_more_than_one_failure(self):
        """It could not: the second write threw and the counter never advanced.

        `write_record` treated a rewrite in the same phase as an illegal
        transition, so `record_failure` succeeded once and then raised
        `StateStoreError` - which means the CLI-side lockout has never counted
        past one.
        """
        store = LocalStateStore(tempfile.mkdtemp())
        limiter = FileAttemptLimiter(
            store=store, max_failures=3, lockout_seconds=30, clock=lambda: 1000
        )
        for _ in range(3):
            limiter.record_failure("cli")
        self.assertFalse(limiter.check("cli").allowed)

    def test_file_limiter_persists_state(self):
        tmpdir = tempfile.mkdtemp()
        store = LocalStateStore(tmpdir)
        limiter = FileAttemptLimiter(
            store=store,
            max_failures=1,
            lockout_seconds=30,
            clock=lambda: 1000,
        )
        limiter.record_failure("cli")

        restored = FileAttemptLimiter(
            store=store,
            max_failures=1,
            lockout_seconds=30,
            clock=lambda: 1000,
        )

        self.assertFalse(restored.check("cli").allowed)


if __name__ == "__main__":
    unittest.main()
