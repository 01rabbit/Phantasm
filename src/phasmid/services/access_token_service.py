from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
from typing import Any

from ..config import state_dir
from ..local_state_crypto import LocalStateCipher

ROLE_STORE = "store"
ROLE_RECOVER = "recover"
ROLES = (ROLE_STORE, ROLE_RECOVER)

_TOKEN_BLOB_NAME = "access_tokens.bin"
_TOKEN_KEY_NAME = "access_tokens.key"
_TOKEN_BYTES = 32


class AccessTokenRoleAlreadyIssued(ValueError):
    """A token for this role already exists; revoke it before reissuing."""


class AccessTokenGadgetRequired(RuntimeError):
    """Token issuance requires a live USB gadget connection."""


class AccessTokenService:
    """Issues and verifies the two WebUI role tokens: store and recover.

    Only a hash of each issued token is ever persisted (encrypted at rest,
    same primitive as the object-cue reference state in ``ai_gate.py``), so a
    seized state directory yields no usable credential. Verification walks
    every stored record rather than short-circuiting on the first match, so
    how long it takes does not depend on which role - or whether any -
    matched.
    """

    def __init__(self, state_directory: str | None = None) -> None:
        self.state_directory = state_directory or state_dir()
        os.makedirs(self.state_directory, mode=0o700, exist_ok=True)
        self.blob_path = os.path.join(self.state_directory, _TOKEN_BLOB_NAME)
        self.key_path = os.path.join(self.state_directory, _TOKEN_KEY_NAME)
        self.cipher = LocalStateCipher(
            state_key_path=self.key_path,
            aad=f"phasmid-access-tokens-v1:{os.path.basename(self.blob_path)}".encode(
                "utf-8"
            ),
        )

    def _validate_role(self, role: str) -> None:
        if role not in ROLES:
            raise ValueError(f"unsupported access token role: {role}")

    def _load(self) -> dict[str, Any]:
        if not os.path.exists(self.blob_path):
            return {}
        with open(self.blob_path, "rb") as handle:
            payload = handle.read()
        if not payload:
            return {}
        plaintext = self.cipher.decrypt(
            payload,
            too_short_message="access token store is too short",
            auth_failed_message="access token store authentication failed",
        )
        data = json.loads(plaintext.decode("utf-8"))
        return data if isinstance(data, dict) else {}

    def _save(self, data: dict[str, Any]) -> None:
        plaintext = json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )
        payload = self.cipher.encrypt(plaintext)
        with open(self.blob_path, "wb") as handle:
            handle.write(payload)
        try:
            os.chmod(self.blob_path, 0o600)
        except OSError:
            pass

    def has_token(self, role: str) -> bool:
        self._validate_role(role)
        return role in self._load()

    def issued_roles(self) -> dict[str, str]:
        """Return {role: issued_at} for every currently-issued token."""
        data = self._load()
        return {
            role: str(data[role].get("issued_at", "")) for role in ROLES if role in data
        }

    def issue(self, role: str, *, gadget_ip: str | None) -> str:
        """Issue a new token for ``role`` and return the raw value.

        The raw token is returned exactly once here and never again - only
        its salted hash is persisted. ``gadget_ip`` must be a detected USB
        gadget address; callers resolve this themselves (see
        ``WebUIService.gadget_ip()``) so this service has no subprocess
        dependency of its own. Issuing over Wi-Fi or from across a room,
        rather than tethered to the device, defeats the reason a second
        credential tier exists at all.
        """
        self._validate_role(role)
        if not gadget_ip:
            raise AccessTokenGadgetRequired(
                "a USB gadget connection is required to issue an access token"
            )
        data = self._load()
        if role in data:
            raise AccessTokenRoleAlreadyIssued(
                f"a {role} token is already issued; revoke it before reissuing"
            )
        token = secrets.token_urlsafe(_TOKEN_BYTES)
        salt = os.urandom(16)
        digest = hashlib.sha256(salt + token.encode("utf-8")).digest()
        data[role] = {
            "salt_b64": base64.b64encode(salt).decode("ascii"),
            "hash_b64": base64.b64encode(digest).decode("ascii"),
            "issued_at": self._timestamp(),
        }
        self._save(data)
        return token

    def revoke(self, role: str) -> bool:
        """Clear the issued token for ``role``. Returns False if none existed."""
        self._validate_role(role)
        data = self._load()
        if role not in data:
            return False
        del data[role]
        self._save(data)
        return True

    def verify(self, token: str) -> str | None:
        """Return the role ``token`` belongs to, or None if it matches neither."""
        if not token:
            return None
        data = self._load()
        matched_role: str | None = None
        for role in ROLES:
            record = data.get(role)
            if not isinstance(record, dict):
                continue
            try:
                salt = base64.b64decode(str(record.get("salt_b64", "")).encode("ascii"))
                expected = base64.b64decode(
                    str(record.get("hash_b64", "")).encode("ascii")
                )
            except (ValueError, TypeError):
                continue
            actual = hashlib.sha256(salt + token.encode("utf-8")).digest()
            if secrets.compare_digest(actual, expected):
                matched_role = role
        return matched_role

    def _timestamp(self) -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


access_token_service = AccessTokenService()
