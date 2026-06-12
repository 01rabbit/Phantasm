"""Reviewable local cryptographic primitive boundary and self-tests."""

from __future__ import annotations

import hashlib
import hmac
import os
import threading

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class CryptoSelfTestError(RuntimeError):
    """Raised when a required local primitive check fails."""


_SELF_TEST_PASSED = False
_SELF_TEST_LOCK = threading.Lock()


def ensure_crypto_self_tests():
    global _SELF_TEST_PASSED
    if _SELF_TEST_PASSED:
        return True
    with _SELF_TEST_LOCK:
        if _SELF_TEST_PASSED:
            return True
        try:
            _check_aes_gcm()
            _check_hmac_sha256()
            _check_random_bytes()
        except Exception as exc:
            raise CryptoSelfTestError("cryptographic self-test failed") from exc
        _SELF_TEST_PASSED = True
    return True


def random_bytes(length: int):
    if length <= 0:
        raise ValueError("length must be positive")
    return os.urandom(length)


def _check_aes_gcm():
    key = bytes.fromhex("00" * 31 + "01")
    nonce = bytes.fromhex("00" * 11 + "01")
    aad = b"phasmid-self-test"
    plaintext = b"local primitive check"
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, aad)
    recovered = aesgcm.decrypt(nonce, ciphertext, aad)
    if recovered != plaintext:
        raise CryptoSelfTestError("aes-gcm check failed")


def _check_hmac_sha256():
    digest = hmac.new(b"phasmid", b"self-test", hashlib.sha256).hexdigest()
    expected = "03d2b411e899d25f487010c32f26d23dfed38d041c49714ef3709f0388d163a3"
    if not hmac.compare_digest(digest, expected):
        raise CryptoSelfTestError("hmac check failed")


def _check_random_bytes():
    first = random_bytes(32)
    second = random_bytes(32)
    if len(first) != 32 or len(second) != 32 or first == second:
        raise CryptoSelfTestError("random byte check failed")
