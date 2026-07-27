import os
import tempfile
import unittest

from src.phasmid import crypto_params
from src.phasmid.container_layout import ContainerLayout
from src.phasmid.record_cypher import RecordCipher


class ContainerFormatConstantsTests(unittest.TestCase):
    def test_record_cipher_format_values_are_locked(self):
        self.assertEqual(RecordCipher.FORMAT_VERSION, 3)
        self.assertEqual(RecordCipher.FORMAT_MARKER, "jes-v3")
        self.assertEqual(RecordCipher.SALT_SIZE, 16)
        self.assertEqual(RecordCipher.NONCE_SIZE, 12)
        self.assertEqual(RecordCipher.AESGCM_TAG_SIZE, 16)
        self.assertEqual(RecordCipher.RECORD_OVERHEAD, 44)
        self.assertEqual(RecordCipher.OPEN_ROLE, "open")
        self.assertEqual(RecordCipher.PURGE_ROLE, "purge")
        self.assertEqual(RecordCipher.SLOT_ROLES, ("open", "purge"))

    def test_crypto_params_version_matches_record_cipher(self):
        self.assertEqual(crypto_params.FORMAT_VERSION, 3)
        self.assertEqual(crypto_params.VAULT_FORMAT_VERSION, 3)
        self.assertEqual(crypto_params.FORMAT_MARKER, "jes-v3")
        self.assertEqual(crypto_params.SALT_SIZE, 16)
        self.assertEqual(crypto_params.NONCE_SIZE, 12)
        self.assertEqual(crypto_params.TAG_SIZE, 16)
        self.assertEqual(crypto_params.RECORD_OVERHEAD, 44)
        self.assertEqual(crypto_params.OPEN_ROLE, "open")
        self.assertEqual(crypto_params.PURGE_ROLE, "purge")
        self.assertEqual(crypto_params.SLOT_ROLES, ("open", "purge"))
        self.assertEqual(
            crypto_params.VAULT_FORMAT_VERSION,
            RecordCipher.FORMAT_VERSION,
        )
        self.assertEqual(crypto_params.FORMAT_MARKER, RecordCipher.FORMAT_MARKER)
        self.assertEqual(crypto_params.SALT_SIZE, RecordCipher.SALT_SIZE)
        self.assertEqual(crypto_params.NONCE_SIZE, RecordCipher.NONCE_SIZE)
        self.assertEqual(crypto_params.TAG_SIZE, RecordCipher.AESGCM_TAG_SIZE)
        self.assertEqual(
            crypto_params.RECORD_OVERHEAD,
            RecordCipher.RECORD_OVERHEAD,
        )
        self.assertEqual(crypto_params.OPEN_ROLE, RecordCipher.OPEN_ROLE)
        self.assertEqual(crypto_params.PURGE_ROLE, RecordCipher.PURGE_ROLE)
        self.assertEqual(crypto_params.SLOT_ROLES, RecordCipher.SLOT_ROLES)

    def test_container_layout_capacity_uses_record_overhead(self):
        with tempfile.NamedTemporaryFile(delete=False) as handle:
            container_path = handle.name
        self.addCleanup(
            lambda: os.path.exists(container_path) and os.unlink(container_path)
        )

        container_size = 4096
        layout = ContainerLayout(container_path, container_size)
        _start, slot_len = layout.get_slot_span("dummy", "open")

        self.assertEqual(
            slot_len - layout.get_plaintext_capacity("dummy", "open"),
            RecordCipher.RECORD_OVERHEAD,
        )


if __name__ == "__main__":
    unittest.main()
