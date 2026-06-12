import json
import os
import struct
import time

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .crypto_params import (
    FORMAT_MARKER,
    FORMAT_VERSION,
    NONCE_SIZE,
    OPEN_ROLE,
    PURGE_ROLE,
    RECORD_OVERHEAD,
    SALT_SIZE,
    SLOT_ROLES,
    TAG_SIZE,
)


class RecordCipher:
    FORMAT_VERSION = FORMAT_VERSION
    FORMAT_MARKER = FORMAT_MARKER
    AESGCM_TAG_SIZE = TAG_SIZE
    SALT_SIZE = SALT_SIZE
    NONCE_SIZE = NONCE_SIZE
    RECORD_OVERHEAD = RECORD_OVERHEAD
    OPEN_ROLE = OPEN_ROLE
    PURGE_ROLE = PURGE_ROLE
    SLOT_ROLES = SLOT_ROLES

    def __init__(self, container_path, container_size, container_layout):
        self.container_path = container_path
        self.container_size = container_size
        self.container_layout = container_layout

    def _record_aad(self, mode, password_role):
        return f"phasmid-record-v3:{mode}:{password_role}:{self.container_size}".encode(
            "utf-8"
        )

    def encrypt_record(
        self,
        plaintext: bytes,
        key: bytes,
        mode: str,
        password_role: str,
        filename: str | None = "payload.bin",
        payload_len: int | None = None,
        created_at: int | None = None,
        salt: bytes | None = None,
    ) -> tuple[bytes, bytes, bytes]:
        """Encrypt a record and return (salt, nonce, ciphertext)"""
        if payload_len is None:
            payload_len = len(plaintext)
        if created_at is None:
            created_at = int(time.time())
        if salt is None:
            salt = os.urandom(self.SALT_SIZE)

        nonce = os.urandom(self.NONCE_SIZE)
        aesgcm = AESGCM(key)

        metadata = {
            "format": self.FORMAT_MARKER,
            "version": self.FORMAT_VERSION,
            "password_role": password_role,
            "filename": os.path.basename(filename or "payload.bin"),
            "payload_len": payload_len,
            "created_at": created_at,
            "kdf": "argon2id",
        }
        metadata_bytes = json.dumps(
            metadata, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")

        required_len = 4 + len(metadata_bytes) + len(plaintext)
        capacity = self.container_layout.get_plaintext_capacity(mode, password_role)
        padding_len = capacity - required_len
        if padding_len < 0:
            raise ValueError("encrypted payload does not fit in the container")
        padding = os.urandom(padding_len)
        record_plaintext = (
            struct.pack(">I", len(metadata_bytes))
            + metadata_bytes
            + plaintext
            + padding
        )
        aad = self._record_aad(mode, password_role)
        ciphertext = aesgcm.encrypt(nonce, record_plaintext, aad)

        return salt, nonce, ciphertext

    def decrypt_record(
        self,
        ciphertext: bytes,
        key: bytes,
        salt: bytes,
        nonce: bytes,
        mode: str,
        password_role: str,
    ) -> tuple[bytes, str, dict]:
        """Decrypt a record and return (data, filename, metadata) or raise exception"""
        aesgcm = AESGCM(key)
        aad = self._record_aad(mode, password_role)
        decrypted = aesgcm.decrypt(nonce, ciphertext, aad)

        if len(decrypted) < 4:
            raise ValueError("decrypted record too short")

        meta_len = struct.unpack(">I", decrypted[:4])[0]
        if meta_len > len(decrypted) - 4:
            raise ValueError("invalid metadata length")

        metadata = json.loads(decrypted[4 : 4 + meta_len].decode("utf-8"))
        if (
            metadata.get("format") != self.FORMAT_MARKER
            or metadata.get("version") != self.FORMAT_VERSION
        ):
            raise ValueError("invalid record format or version")

        if metadata.get("password_role") != password_role:
            raise ValueError("password role mismatch")

        payload_len = metadata.get("payload_len")
        if not isinstance(payload_len, int) or payload_len < 0:
            raise ValueError("invalid payload length")

        payload_start = 4 + meta_len
        payload_end = payload_start + payload_len
        if payload_end > len(decrypted):
            raise ValueError("payload length exceeds decrypted data")

        actual_data = decrypted[payload_start:payload_end]
        filename = os.path.basename(metadata.get("filename") or "payload.bin")

        return actual_data, filename, metadata
