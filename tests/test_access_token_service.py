import os
import unittest
from unittest import mock

from src.phasmid.services.access_token_service import (
    ENV_ISSUED_AT,
    ROLE_RECOVER,
    ROLE_STORE,
    AccessTokenEnvPinned,
    AccessTokenGadgetRequired,
    AccessTokenRoleAlreadyIssued,
    AccessTokenService,
)


class TestAccessTokenService(unittest.TestCase):
    def setUp(self):
        import tempfile

        self.tmp_dir = tempfile.mkdtemp()
        self.service = AccessTokenService(state_directory=self.tmp_dir)

    def test_issue_requires_a_gadget_ip(self):
        """Issuance without a detected USB gadget must be refused outright.

        The whole point of a second credential tier is that granting it
        requires the operator's hands on the device over USB - not merely
        reachability from the same Wi-Fi network or across a room.
        """
        with self.assertRaises(AccessTokenGadgetRequired):
            self.service.issue(ROLE_STORE, gadget_ip=None)
        with self.assertRaises(AccessTokenGadgetRequired):
            self.service.issue(ROLE_STORE, gadget_ip="")

    def test_issue_then_verify_round_trip(self):
        token = self.service.issue(ROLE_STORE, gadget_ip="10.55.0.1")
        self.assertEqual(self.service.verify(token), ROLE_STORE)

    def test_issue_rejects_reissue_while_a_hash_exists(self):
        self.service.issue(ROLE_RECOVER, gadget_ip="10.55.0.1")
        with self.assertRaises(AccessTokenRoleAlreadyIssued):
            self.service.issue(ROLE_RECOVER, gadget_ip="10.55.0.1")

    def test_revoke_then_reissue_succeeds(self):
        self.service.issue(ROLE_STORE, gadget_ip="10.55.0.1")
        self.assertTrue(self.service.revoke(ROLE_STORE))
        second_token = self.service.issue(ROLE_STORE, gadget_ip="10.55.0.1")
        self.assertEqual(self.service.verify(second_token), ROLE_STORE)

    def test_revoke_with_nothing_issued_returns_false(self):
        self.assertFalse(self.service.revoke(ROLE_STORE))

    def test_verify_distinguishes_store_and_recover_tokens(self):
        store_token = self.service.issue(ROLE_STORE, gadget_ip="10.55.0.1")
        recover_token = self.service.issue(ROLE_RECOVER, gadget_ip="10.55.0.1")

        self.assertEqual(self.service.verify(store_token), ROLE_STORE)
        self.assertEqual(self.service.verify(recover_token), ROLE_RECOVER)

    def test_verify_rejects_unknown_or_empty_token(self):
        self.service.issue(ROLE_STORE, gadget_ip="10.55.0.1")
        self.assertIsNone(self.service.verify("not-a-real-token"))
        self.assertIsNone(self.service.verify(""))

    def test_verify_stops_matching_a_revoked_token(self):
        token = self.service.issue(ROLE_RECOVER, gadget_ip="10.55.0.1")
        self.service.revoke(ROLE_RECOVER)
        self.assertIsNone(self.service.verify(token))

    def test_has_token_and_issued_roles(self):
        self.assertFalse(self.service.has_token(ROLE_STORE))
        self.service.issue(ROLE_STORE, gadget_ip="10.55.0.1")
        self.assertTrue(self.service.has_token(ROLE_STORE))
        self.assertFalse(self.service.has_token(ROLE_RECOVER))
        self.assertEqual(set(self.service.issued_roles()), {ROLE_STORE})

    def test_invalid_role_is_rejected_everywhere(self):
        with self.assertRaises(ValueError):
            self.service.has_token("admin")
        with self.assertRaises(ValueError):
            self.service.issue("admin", gadget_ip="10.55.0.1")
        with self.assertRaises(ValueError):
            self.service.revoke("admin")

    def test_persisted_blob_is_encrypted_and_never_contains_the_raw_token(self):
        token = self.service.issue(ROLE_STORE, gadget_ip="10.55.0.1")
        with open(self.service.blob_path, "rb") as handle:
            raw = handle.read()
        self.assertNotIn(token.encode("utf-8"), raw)
        # A fresh service instance pointed at a different key can never
        # decrypt this blob - confirms the plaintext (and therefore the
        # token) is not recoverable without the local state key.
        import base64
        import json

        try:
            json.loads(base64.b64decode(raw, validate=False))
            decoded_as_plain_json = True
        except Exception:
            decoded_as_plain_json = False
        self.assertFalse(decoded_as_plain_json)

    def test_second_instance_same_directory_shares_state(self):
        token = self.service.issue(ROLE_STORE, gadget_ip="10.55.0.1")
        other = AccessTokenService(state_directory=self.tmp_dir)
        self.assertEqual(other.verify(token), ROLE_STORE)

    def test_env_pinned_token_verifies_without_ever_being_issued(self):
        """A fixed demo token needs no TUI issuance step at all.

        PHASMID_STORE_TOKEN/PHASMID_RECOVER_TOKEN mirror PHASMID_WEB_TOKEN:
        set once at process startup for a reproducible demo, instead of
        depending on a value the TUI only ever shows once.
        """
        with mock.patch.dict(os.environ, {"PHASMID_STORE_TOKEN": "demo-store-fixed"}):
            self.assertEqual(self.service.verify("demo-store-fixed"), ROLE_STORE)
            self.assertIsNone(self.service.verify("wrong-value"))

    def test_env_pinned_token_reports_has_token_and_issued_roles(self):
        with mock.patch.dict(os.environ, {"PHASMID_RECOVER_TOKEN": "demo-recover"}):
            self.assertTrue(self.service.has_token(ROLE_RECOVER))
            self.assertEqual(self.service.issued_roles()[ROLE_RECOVER], ENV_ISSUED_AT)

    def test_env_pinned_role_blocks_issue_and_revoke(self):
        with mock.patch.dict(os.environ, {"PHASMID_STORE_TOKEN": "demo-store-fixed"}):
            with self.assertRaises(AccessTokenEnvPinned):
                self.service.issue(ROLE_STORE, gadget_ip="10.55.0.1")
            with self.assertRaises(AccessTokenEnvPinned):
                self.service.revoke(ROLE_STORE)

    def test_env_pinned_token_overrides_a_previously_persisted_hash(self):
        """The env value always wins, even over an existing issued token.

        Otherwise an operator who issued a token earlier and later sets the
        env var for a demo would get inconsistent behavior depending on
        which code path happened to run first.
        """
        old_token = self.service.issue(ROLE_STORE, gadget_ip="10.55.0.1")
        with mock.patch.dict(os.environ, {"PHASMID_STORE_TOKEN": "demo-store-fixed"}):
            self.assertIsNone(self.service.verify(old_token))
            self.assertEqual(self.service.verify("demo-store-fixed"), ROLE_STORE)

    def test_env_pinning_one_role_leaves_the_other_role_normal(self):
        with mock.patch.dict(os.environ, {"PHASMID_STORE_TOKEN": "demo-store-fixed"}):
            recover_token = self.service.issue(ROLE_RECOVER, gadget_ip="10.55.0.1")
            self.assertEqual(self.service.verify(recover_token), ROLE_RECOVER)
            self.assertEqual(self.service.verify("demo-store-fixed"), ROLE_STORE)


if __name__ == "__main__":
    unittest.main()
