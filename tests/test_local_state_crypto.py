import os
import tempfile
import unittest

from src.phasmid.local_state_crypto import LocalStateCipher


class LocalStateCipherTests(unittest.TestCase):
    def test_encrypt_decrypt_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            cipher = LocalStateCipher(
                state_key_path=os.path.join(tmp, "state.key"),
                aad=b"test-aad",
            )

            payload = cipher.encrypt(b"local state payload")

            self.assertEqual(
                cipher.decrypt(
                    payload,
                    too_short_message="too short",
                    auth_failed_message="auth failed",
                ),
                b"local state payload",
            )

    def test_decrypt_rejects_wrong_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            writer = LocalStateCipher(
                state_key_path=os.path.join(tmp, "writer.key"),
                aad=b"test-aad",
            )
            reader = LocalStateCipher(
                state_key_path=os.path.join(tmp, "reader.key"),
                aad=b"test-aad",
            )
            payload = writer.encrypt(b"local state payload")

            with self.assertRaisesRegex(ValueError, "auth failed"):
                reader.decrypt(
                    payload,
                    too_short_message="too short",
                    auth_failed_message="auth failed",
                )

    def test_decrypt_rejects_corrupted_blob(self):
        with tempfile.TemporaryDirectory() as tmp:
            cipher = LocalStateCipher(
                state_key_path=os.path.join(tmp, "state.key"),
                aad=b"test-aad",
            )
            payload = bytearray(cipher.encrypt(b"local state payload"))
            payload[-1] ^= 0x01

            with self.assertRaisesRegex(ValueError, "auth failed"):
                cipher.decrypt(
                    bytes(payload),
                    too_short_message="too short",
                    auth_failed_message="auth failed",
                )

    def test_decrypt_rejects_short_blob(self):
        with tempfile.TemporaryDirectory() as tmp:
            cipher = LocalStateCipher(
                state_key_path=os.path.join(tmp, "state.key"),
                aad=b"test-aad",
            )

            with self.assertRaisesRegex(ValueError, "too short"):
                cipher.decrypt(
                    b"short",
                    too_short_message="too short",
                    auth_failed_message="auth failed",
                )


if __name__ == "__main__":
    unittest.main()
