import json
import os

from cryptography.exceptions import InvalidTag

from .config import VAULT_KEY_NAME
from .config import state_dir as default_state_dir
from .container_layout import ContainerLayout
from .crypto_params import (
    ARGON2_ITERATIONS,
    ARGON2_LANES,
    ARGON2_MEMORY_COST,
    VAULT_FORMAT_VERSION,
)
from .kdf_engine import KDFEngine
from .record_cypher import RecordCipher


class PhasmidVault:
    FORMAT_VERSION = VAULT_FORMAT_VERSION
    MIN_CONTAINER_SIZE = 4096
    ARGON2_ITERATIONS = ARGON2_ITERATIONS
    ARGON2_LANES = ARGON2_LANES
    ARGON2_MEMORY_COST = ARGON2_MEMORY_COST
    SALT_SIZE = RecordCipher.SALT_SIZE
    NONCE_SIZE = RecordCipher.NONCE_SIZE
    OPEN_ROLE = RecordCipher.OPEN_ROLE
    PURGE_ROLE = RecordCipher.PURGE_ROLE
    SLOT_ROLES = RecordCipher.SLOT_ROLES

    def __init__(
        self,
        container_path: str,
        size_mb: int | float | str = 10,
        state_dir: str | None = None,
    ) -> None:
        self.path = container_path
        self.size = self._normalize_size(size_mb)
        self.state_dir = state_dir or default_state_dir()
        self.access_key_path = os.path.join(self.state_dir, VAULT_KEY_NAME)
        self.kdf_engine = KDFEngine(self.state_dir)
        self.container_layout = ContainerLayout(self.path, self.size)
        self.record_cipher = RecordCipher(self.path, self.size, self.container_layout)

    def _normalize_size(self, size_mb: int | float | str) -> int:
        try:
            size_bytes = int(float(size_mb) * 1024 * 1024)
        except (TypeError, ValueError) as exc:
            raise ValueError("size_mb must be a positive number") from exc

        if size_bytes < self.MIN_CONTAINER_SIZE:
            raise ValueError(
                f"container size must be at least {self.MIN_CONTAINER_SIZE} bytes"
            )
        return size_bytes

    def _derive_key(
        self,
        password: str,
        gesture_sequence: list[str],
        mode: str,
        salt: bytes,
        create_access_key: bool = False,
        password_role: str = OPEN_ROLE,
    ) -> bytes:
        return self.kdf_engine.derive_key(
            password=password,
            gesture_sequence=gesture_sequence,
            mode=mode,
            salt=salt,
            password_role=password_role,
            create_access_key=create_access_key,
        )

    def _load_or_create_access_key(self, create: bool = False) -> bytes | None:
        return self.kdf_engine._load_or_create_access_key(create=create)

    def rotate_access_key(self) -> None:
        self.kdf_engine.rotate_access_key()

    def format_container(self, rotate_access_key: bool = False) -> None:
        if rotate_access_key:
            self.rotate_access_key()
        else:
            self._load_or_create_access_key(create=True)
        self.container_layout.format_container()

    def store(
        self,
        password: str,
        data: bytes,
        gesture_sequence: list[str],
        filename: str | None = "payload.bin",
        mode: str = "dummy",
        restricted_recovery_password: str | None = None,
    ) -> None:
        self.container_layout._require_container()
        if (
            restricted_recovery_password is not None
            and restricted_recovery_password == password
        ):
            raise ValueError("open and restricted recovery passwords must be different")

        self._write_slot(
            password,
            data,
            gesture_sequence,
            filename=filename,
            mode=mode,
            password_role=self.OPEN_ROLE,
        )

        if restricted_recovery_password:
            self._write_slot(
                restricted_recovery_password,
                data,
                gesture_sequence,
                filename=filename,
                mode=mode,
                password_role=self.PURGE_ROLE,
            )
        else:
            self._randomize_slot(mode, self.PURGE_ROLE)

    def _write_slot(
        self,
        password: str,
        data: bytes,
        gesture_sequence: list[str],
        filename: str | None,
        mode: str,
        password_role: str,
    ) -> None:
        start, span_len = self.container_layout.get_slot_span(mode, password_role)

        salt = os.urandom(self.record_cipher.SALT_SIZE)
        key = self._derive_key(
            password,
            gesture_sequence,
            mode,
            salt,
            create_access_key=True,
            password_role=password_role,
        )
        salt, nonce, ciphertext = self.record_cipher.encrypt_record(
            data,
            key,
            mode,
            password_role,
            filename,
            salt=salt,
        )
        payload = salt + nonce + ciphertext
        padding_len = span_len - len(payload)
        if padding_len > 0:
            payload += os.urandom(padding_len)

        with open(self.path, "r+b") as f:
            f.seek(start)
            f.write(payload)

    def retrieve(
        self, password: str, gesture_sequence: list[str], mode: str = "dummy"
    ) -> tuple[bytes | None, str | None]:
        data, filename, _password_role = self.retrieve_with_policy(
            password, gesture_sequence, mode=mode
        )
        return data, filename

    def retrieve_with_policy(
        self, password: str, gesture_sequence: list[str], mode: str = "dummy"
    ) -> tuple[bytes | None, str | None, str | None]:
        self.container_layout._require_container()
        for password_role in self.SLOT_ROLES:
            data, filename = self._retrieve_slot(
                password, gesture_sequence, mode, password_role
            )
            if data is not None:
                return data, filename, password_role
        return None, None, None

    def _retrieve_slot(
        self,
        password: str,
        gesture_sequence: list[str],
        mode: str,
        password_role: str,
    ) -> tuple[bytes | None, str | None]:
        start, span_len = self.container_layout.get_slot_span(mode, password_role)
        ciphertext_len = (
            span_len - self.record_cipher.SALT_SIZE - self.record_cipher.NONCE_SIZE
        )

        with open(self.path, "rb") as f:
            f.seek(start)
            salt = f.read(self.record_cipher.SALT_SIZE)
            nonce = f.read(self.record_cipher.NONCE_SIZE)
            ciphertext = f.read(ciphertext_len)
            if (
                len(salt) != self.record_cipher.SALT_SIZE
                or len(nonce) != self.record_cipher.NONCE_SIZE
            ):
                return None, None
            if len(ciphertext) != ciphertext_len:
                return None, None

        try:
            key = self._derive_key(
                password,
                gesture_sequence,
                mode,
                salt,
                create_access_key=False,
                password_role=password_role,
            )
            data, filename, _metadata = self.record_cipher.decrypt_record(
                ciphertext, key, salt, nonce, mode, password_role
            )
            return data, filename
        except (
            InvalidTag,
            ValueError,
            OSError,
            json.JSONDecodeError,
            UnicodeDecodeError,
            KeyError,
        ):
            return None, None

    def _randomize_slot(self, mode: str, password_role: str) -> None:
        self.container_layout.randomize_slot(mode, password_role)

    def silent_brick(self) -> None:
        self.destroy_access_keys()
        self.container_layout.silent_brick()

    def destroy_access_keys(self) -> None:
        self.kdf_engine.destroy_access_keys()

    def purge_mode(self, mode: str) -> None:
        self.container_layout.purge_mode(mode)

    def purge_other_mode(self, accessed_mode: str) -> None:
        self.container_layout.purge_other_mode(accessed_mode)
