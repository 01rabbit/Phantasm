from __future__ import annotations

import io
import logging
import os
from typing import Any, Callable

import numpy as np

from .local_state_crypto import LocalStateCipher

LOG = logging.getLogger(__name__)


class ObjectCueStore:
    """Persistence layer for encrypted object-cue template state."""

    def __init__(
        self,
        *,
        modes: tuple[str, ...],
        state_blob_path: str,
        state_cipher: LocalStateCipher,
        empty_reference: Callable[[], dict[str, object | None]],
        state_to_arrays: Callable[[dict[str, object]], dict[str, np.ndarray]],
        reference_from_arrays: Callable[
            [np.ndarray, np.ndarray, np.ndarray], dict[str, object | None]
        ],
    ) -> None:
        self.modes = modes
        self.state_blob_path = state_blob_path
        self.state_cipher = state_cipher
        self.empty_reference = empty_reference
        self.state_to_arrays = state_to_arrays
        self.reference_from_arrays = reference_from_arrays

    def save(self, references: dict[str, dict[str, object | None]]) -> None:
        template = io.BytesIO()
        payload: dict[str, Any] = {}
        for mode in self.modes:
            state = references.get(mode) or self.empty_reference()
            if state["des"] is None:
                payload[f"{mode}_present"] = np.array([0], dtype=np.uint8)
                payload[f"{mode}_des"] = np.empty((0, 32), dtype=np.uint8)
                payload[f"{mode}_kp"] = np.empty((0, 7), dtype=np.float32)
                payload[f"{mode}_shape"] = np.array([0, 0], dtype=np.int32)
                continue
            arrays = self.state_to_arrays(state)
            payload[f"{mode}_present"] = np.array([1], dtype=np.uint8)
            payload[f"{mode}_des"] = arrays["des"]
            payload[f"{mode}_kp"] = arrays["kp"]
            payload[f"{mode}_shape"] = arrays["shape"]

        np.savez_compressed(template, **payload)
        encrypted = self.state_cipher.encrypt(template.getvalue())
        with open(self.state_blob_path, "wb") as handle:
            handle.write(encrypted)
        try:
            os.chmod(self.state_blob_path, 0o600)
        except OSError as exc:
            LOG.debug("object cue state permission update failed: %s", exc)

    def load(self) -> dict[str, dict[str, object | None]]:
        references = {mode: self.empty_reference() for mode in self.modes}
        if not os.path.exists(self.state_blob_path):
            return references

        try:
            with open(self.state_blob_path, "rb") as handle:
                payload = handle.read()
            plaintext = self.state_cipher.decrypt(
                payload,
                too_short_message="reference template is too short",
                auth_failed_message="reference template authentication failed",
            )
            with np.load(io.BytesIO(plaintext), allow_pickle=False) as template:
                for mode in self.modes:
                    if int(template[f"{mode}_present"][0]) != 1:
                        continue
                    references[mode] = self.reference_from_arrays(
                        template[f"{mode}_des"],
                        template[f"{mode}_kp"],
                        template[f"{mode}_shape"],
                    )
        except Exception as exc:
            LOG.debug("object cue state load failed: %s", exc)
            return {mode: self.empty_reference() for mode in self.modes}

        return references
