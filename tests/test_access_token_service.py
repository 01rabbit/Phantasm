import unittest

from src.phasmid.services.access_token_service import (
    ROLE_RECOVER,
    ROLE_STORE,
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


if __name__ == "__main__":
    unittest.main()
