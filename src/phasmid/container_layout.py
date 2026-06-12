import os

from .crypto_params import OPEN_ROLE, RECORD_OVERHEAD, SLOT_ROLES


class ContainerLayout:
    MIN_CONTAINER_SIZE = 4096

    def __init__(self, container_path: str, container_size: int):
        self.container_path = container_path
        self.container_size = container_size

    def _require_container(self):
        if not os.path.exists(self.container_path):
            raise FileNotFoundError(
                f"container file not found: {self.container_path}. Run format_container() first."
            )

    def get_mode_span(self, mode: str) -> tuple[int, int]:
        """Get the span for a mode"""
        if mode == "secret":
            return self.container_size // 2, self.container_size - (
                self.container_size // 2
            )
        if mode == "dummy":
            return 0, self.container_size // 2
        raise ValueError(f"unsupported mode: {mode}")

    def get_slot_span(self, mode: str, password_role: str) -> tuple[int, int]:
        """Get the span for a slot within a mode"""
        if password_role not in SLOT_ROLES:
            raise ValueError(f"unsupported password role: {password_role}")
        start, span_len = self.get_mode_span(mode)
        first_slot_len = span_len // 2
        if password_role == OPEN_ROLE:
            return start, first_slot_len
        return start + first_slot_len, span_len - first_slot_len

    def get_plaintext_capacity(self, mode: str, password_role: str) -> int:
        """Calculate plaintext capacity for a specific slot"""
        _start, span_len = self.get_slot_span(mode, password_role)
        capacity = span_len - RECORD_OVERHEAD
        if capacity <= 4:
            raise ValueError("container is too small for encrypted record")
        return capacity

    def format_container(self, rotate_access_key=False):
        """Initialize a new container file with random data"""
        # Note: rotate_access_key is handled by KDFEngine, just format the container
        with open(self.container_path, "wb") as f:
            f.write(os.urandom(self.container_size))
        try:
            os.chmod(self.container_path, 0o600)
        except OSError:
            pass

    def silent_brick(self):
        """Overwrite the entire container with random data"""
        self._require_container()
        with open(self.container_path, "r+b") as f:
            f.seek(0)
            f.write(os.urandom(self.container_size))

    def purge_mode(self, mode: str):
        """Overwrite a mode with random data"""
        self._require_container()
        start, length = self.get_mode_span(mode)
        with open(self.container_path, "r+b") as f:
            f.seek(start)
            f.write(os.urandom(length))

    def randomize_slot(self, mode: str, password_role: str):
        """Randomize a slot by overwriting with random data"""
        self._require_container()
        start, length = self.get_slot_span(mode, password_role)
        with open(self.container_path, "r+b") as f:
            f.seek(start)
            f.write(os.urandom(length))

    def purge_other_mode(self, accessed_mode: str):
        """Purge the mode that was not accessed"""
        if accessed_mode == "dummy":
            self.purge_mode("secret")
            return
        if accessed_mode == "secret":
            self.purge_mode("dummy")
            return
        raise ValueError(f"unsupported mode: {accessed_mode}")
