import os
import tempfile
import unittest

from src.phasmid.container_layout import ContainerLayout
from src.phasmid.crypto_params import OPEN_ROLE


class TestContainerLayout(unittest.TestCase):
    def setUp(self):
        self.container_path = tempfile.mktemp()
        self.container_size = 10 * 1024 * 1024  # 10MB
        self.layout = ContainerLayout(self.container_path, self.container_size)

    def tearDown(self):
        if os.path.exists(self.container_path):
            os.unlink(self.container_path)

    def test_get_mode_span_dummy(self):
        """Test get_mode_span for dummy mode"""
        start, length = self.layout.get_mode_span("dummy")
        self.assertEqual(start, 0)
        self.assertEqual(length, self.container_size // 2)

    def test_get_mode_span_secret(self):
        """Test get_mode_span for secret mode"""
        start, length = self.layout.get_mode_span("secret")
        self.assertEqual(start, self.container_size // 2)
        self.assertEqual(length, self.container_size - (self.container_size // 2))

    def test_get_mode_span_invalid(self):
        """Test get_mode_span raises ValueError for invalid mode"""
        with self.assertRaises(ValueError):
            self.layout.get_mode_span("invalid")

    def test_get_slot_span_open_dummy(self):
        """Test get_slot_span for open role in dummy mode"""
        start, length = self.layout.get_slot_span("dummy", "open")
        expected_start = 0
        expected_length = (self.container_size // 2) // 2
        self.assertEqual(start, expected_start)
        self.assertEqual(length, expected_length)

    def test_get_slot_span_purge_secret(self):
        """Test get_slot_span for purge role in secret mode"""
        start, length = self.layout.get_slot_span("secret", "purge")
        mode_start = self.container_size // 2
        mode_length = self.container_size - mode_start
        expected_start = mode_start + (mode_length // 2)
        expected_length = mode_length - (mode_length // 2)
        self.assertEqual(start, expected_start)
        self.assertEqual(length, expected_length)

    def test_get_slot_span_invalid_role(self):
        """Test get_slot_span raises ValueError for invalid role"""
        with self.assertRaises(ValueError):
            self.layout.get_slot_span("dummy", "invalid")

    def test_get_plaintext_capacity(self):
        """Test get_plaintext_capacity calculation"""
        capacity = self.layout.get_plaintext_capacity("dummy", "open")
        RECORD_OVERHEAD = 16 + 12 + 16  # SALT + NONCE + TAG
        expected_capacity = ((self.container_size // 2) // 2) - RECORD_OVERHEAD
        self.assertEqual(capacity, expected_capacity)

    def test_format_container_creates_file(self):
        """Test format_container creates the container file"""
        self.assertFalse(os.path.exists(self.container_path))
        self.layout.format_container()
        self.assertTrue(os.path.exists(self.container_path))
        with open(self.container_path, "rb") as f:
            data = f.read()
            self.assertEqual(len(data), self.container_size)
            # Should be random, not all zeros
            self.assertNotEqual(data, b"\x00" * self.container_size)

    def test_silent_brick_overwrites_container(self):
        """Test silent_brick overwrites the entire container"""
        # Create container
        self.layout.format_container()
        with open(self.container_path, "rb") as f:
            original_data = f.read()

        # Brick it
        self.layout.silent_brick()
        with open(self.container_path, "rb") as f:
            bricked_data = f.read()

        self.assertEqual(len(bricked_data), self.container_size)
        self.assertNotEqual(original_data, bricked_data)

    def test_purge_mode_dummy(self):
        """Test purge_mode overwrites dummy mode"""
        self.layout.format_container()
        with open(self.container_path, "rb") as f:
            original_data = f.read()

        self.layout.purge_mode("dummy")
        with open(self.container_path, "rb") as f:
            purged_data = f.read()

        # First half should be changed
        self.assertNotEqual(
            original_data[: self.container_size // 2],
            purged_data[: self.container_size // 2],
        )
        # Second half should be unchanged
        self.assertEqual(
            original_data[self.container_size // 2 :],
            purged_data[self.container_size // 2 :],
        )

    def test_purge_mode_secret(self):
        """Test purge_mode overwrites secret mode"""
        self.layout.format_container()
        with open(self.container_path, "rb") as f:
            original_data = f.read()

        self.layout.purge_mode("secret")
        with open(self.container_path, "rb") as f:
            purged_data = f.read()

        # First half should be unchanged
        self.assertEqual(
            original_data[: self.container_size // 2],
            purged_data[: self.container_size // 2],
        )
        # Second half should be changed
        self.assertNotEqual(
            original_data[self.container_size // 2 :],
            purged_data[self.container_size // 2 :],
        )

    def test_purge_other_mode_from_dummy(self):
        """Test purge_other_mode purges secret when dummy was accessed"""
        self.layout.format_container()
        with open(self.container_path, "rb") as f:
            original_data = f.read()

        self.layout.purge_other_mode("dummy")
        with open(self.container_path, "rb") as f:
            purged_data = f.read()

        # Same as purging secret mode
        self.assertEqual(
            original_data[: self.container_size // 2],
            purged_data[: self.container_size // 2],
        )
        self.assertNotEqual(
            original_data[self.container_size // 2 :],
            purged_data[self.container_size // 2 :],
        )

    def test_purge_other_mode_from_secret(self):
        """Test purge_other_mode purges dummy when secret was accessed"""
        self.layout.format_container()
        with open(self.container_path, "rb") as f:
            original_data = f.read()

        self.layout.purge_other_mode("secret")
        with open(self.container_path, "rb") as f:
            purged_data = f.read()

        # Same as purging dummy mode
        self.assertNotEqual(
            original_data[: self.container_size // 2],
            purged_data[: self.container_size // 2],
        )
        self.assertEqual(
            original_data[self.container_size // 2 :],
            purged_data[self.container_size // 2 :],
        )

    def test_purge_other_mode_invalid(self):
        """Test purge_other_mode raises ValueError for invalid mode"""
        with self.assertRaises(ValueError):
            self.layout.purge_other_mode("invalid")

    def test_require_container_missing_file(self):
        """Test _require_container raises FileNotFoundError for missing file"""
        with self.assertRaises(FileNotFoundError):
            self.layout._require_container()

    def _largest_urandom_request(self, action):
        """Run action and report the biggest single os.urandom() it asked for."""
        import src.phasmid.container_layout as module

        requested = []
        real_urandom = module.os.urandom

        def recording_urandom(size):
            requested.append(size)
            return real_urandom(size)

        module.os.urandom = recording_urandom
        try:
            action()
        finally:
            module.os.urandom = real_urandom
        return max(requested)

    def test_random_fill_never_materialises_a_whole_span(self):
        """A span is written in chunks, not allocated whole.

        os.urandom(N) produces N bytes at once, so filling a 512 MiB container
        needed a 512 MiB object. On a 512 MB board that is fatal: the OOM
        killer ended the process when a container was created at the console's
        default size. Every span here is larger than one chunk, so a
        regression to a single call is visible.
        """
        chunk = ContainerLayout._RANDOM_CHUNK
        self.assertLess(chunk, self.container_size // 4, "spans must exceed a chunk")

        self.assertLessEqual(
            self._largest_urandom_request(self.layout.format_container), chunk
        )
        self.assertLessEqual(
            self._largest_urandom_request(self.layout.silent_brick), chunk
        )
        self.assertLessEqual(
            self._largest_urandom_request(lambda: self.layout.purge_mode("dummy")),
            chunk,
        )
        self.assertLessEqual(
            self._largest_urandom_request(
                lambda: self.layout.randomize_slot("dummy", OPEN_ROLE)
            ),
            chunk,
        )

    def test_random_fill_still_covers_the_whole_span(self):
        """Chunking must not shorten what it writes."""
        self.layout.format_container()
        self.assertEqual(os.path.getsize(self.container_path), self.container_size)

        with open(self.container_path, "r+b") as handle:
            handle.seek(0)
            handle.write(b"\x00" * self.container_size)
        self.layout.silent_brick()
        with open(self.container_path, "rb") as handle:
            data = handle.read()
        self.assertEqual(len(data), self.container_size)
        self.assertNotIn(b"\x00" * 4096, data)


if __name__ == "__main__":
    unittest.main()
