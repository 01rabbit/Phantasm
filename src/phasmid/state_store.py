"""Typed local state store with atomic writes and transition checks."""

from __future__ import annotations

import json
import os
import stat
import tempfile
import time
from dataclasses import asdict, dataclass, field
from enum import Enum


@dataclass(frozen=True)
class AttemptState:
    failures: int = 0
    locked_until: int = 0

    def to_dict(self):
        return asdict(self)


from .config import ensure_state_dir, state_dir

SCHEMA_VERSION = 1
STATE_INDEX_NAME = "state_status.json"


class StateStoreError(Exception):
    """Neutral state-store failure."""


class StatePhase(str, Enum):
    UNINITIALIZED = "uninitialized"
    INITIALIZED = "initialized"
    ENROLLED = "enrolled"
    READY = "ready"
    RESTRICTED_PENDING = "restricted_pending"
    BRICKED = "bricked"
    CORRUPT = "corrupt"


ALLOWED_TRANSITIONS = {
    StatePhase.UNINITIALIZED: {
        StatePhase.INITIALIZED,
        StatePhase.CORRUPT,
    },
    StatePhase.INITIALIZED: {
        StatePhase.ENROLLED,
        StatePhase.READY,
        StatePhase.RESTRICTED_PENDING,
        StatePhase.BRICKED,
        StatePhase.CORRUPT,
    },
    StatePhase.ENROLLED: {
        StatePhase.READY,
        StatePhase.RESTRICTED_PENDING,
        StatePhase.BRICKED,
        StatePhase.CORRUPT,
    },
    StatePhase.READY: {
        StatePhase.RESTRICTED_PENDING,
        StatePhase.BRICKED,
        StatePhase.CORRUPT,
    },
    StatePhase.RESTRICTED_PENDING: {
        StatePhase.READY,
        StatePhase.BRICKED,
        StatePhase.CORRUPT,
    },
    StatePhase.BRICKED: {
        StatePhase.INITIALIZED,
        StatePhase.CORRUPT,
    },
    StatePhase.CORRUPT: set(),
}


@dataclass(frozen=True)
class StateRecord:
    category: str
    phase: StatePhase
    schema_version: int = SCHEMA_VERSION
    updated_at: int = 0
    attributes: dict = field(default_factory=dict)

    def to_dict(self):
        data = asdict(self)
        data["phase"] = self.phase.value
        return data

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            raise StateStoreError("state record rejected")
        try:
            schema_version = int(data["schema_version"])
            category = str(data["category"])
            phase = StatePhase(str(data["phase"]))
            updated_at = int(data.get("updated_at", 0))
            attributes = data.get("attributes", {})
        except (KeyError, TypeError, ValueError) as exc:
            raise StateStoreError("state record rejected") from exc
        if schema_version != SCHEMA_VERSION:
            raise StateStoreError("state schema unsupported")
        if not isinstance(attributes, dict):
            raise StateStoreError("state record rejected")
        return cls(
            category=category,
            phase=phase,
            schema_version=schema_version,
            updated_at=updated_at,
            attributes=attributes,
        )


class LocalStateStore:
    def __init__(self, root: str | None = None):
        self.root = root or state_dir()

    def ensure_root(self):
        ensure_state_dir(self.root)

    def path_for(self, name: str):
        if os.path.basename(name) != name:
            raise StateStoreError("state name rejected")
        return os.path.join(self.root, name)

    def read_json(self, name: str):
        path = self.path_for(name)
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def write_json_atomic(self, name: str, data: dict):
        self.ensure_root()
        target_path = self.path_for(name)
        fd, temp_path = tempfile.mkstemp(
            prefix=f".{name}.",
            suffix=".tmp",
            dir=self.root,
            text=True,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, sort_keys=True, separators=(",", ":"))
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temp_path, 0o600)
            os.replace(temp_path, target_path)
            os.chmod(target_path, 0o600)
            self._sync_root()
        except Exception:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise

    def read_record(self, name: str = STATE_INDEX_NAME):
        path = self.path_for(name)
        if not os.path.exists(path):
            return StateRecord(
                category="local_state",
                phase=StatePhase.UNINITIALIZED,
            )
        try:
            return StateRecord.from_dict(self.read_json(name))
        except (OSError, json.JSONDecodeError, StateStoreError):
            return StateRecord(
                category="local_state",
                phase=StatePhase.CORRUPT,
            )

    def write_record(self, record: StateRecord, name: str = STATE_INDEX_NAME):
        current = self.read_record(name)
        if record.phase not in ALLOWED_TRANSITIONS[current.phase]:
            raise StateStoreError("state transition rejected")
        updated = StateRecord(
            category=record.category,
            phase=record.phase,
            schema_version=SCHEMA_VERSION,
            updated_at=int(time.time()),
            attributes=record.attributes,
        )
        self.write_json_atomic(name, updated.to_dict())

    def inspect_layout(self, expected_files=()):
        checks = []
        if not os.path.exists(self.root):
            return {
                "root_present": False,
                "root_secure": False,
                "present_files": [],
                "files_secure": False,
            }
        root_secure = os.path.isdir(self.root) and _secure_mode(
            self.root,
            directory=True,
        )
        present_files = [
            name for name in expected_files if os.path.exists(self.path_for(name))
        ]
        files_secure = all(
            _secure_mode(self.path_for(name), directory=False) for name in present_files
        )
        checks.append(root_secure)
        return {
            "root_present": os.path.isdir(self.root),
            "root_secure": root_secure,
            "present_files": present_files,
            "files_secure": files_secure,
        }

    def _sync_root(self):
        try:
            fd = os.open(self.root, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        except OSError:
            pass


def _secure_mode(path: str, *, directory: bool):
    mode = stat.S_IMODE(os.stat(path).st_mode)
    if directory:
        return (mode & 0o077) == 0
    return (mode & 0o177) == 0
