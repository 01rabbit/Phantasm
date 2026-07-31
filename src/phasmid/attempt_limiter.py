"""Local access-attempt limiter for recovery flows."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict

from .config import access_lockout_seconds, access_max_failures
from .state_store import AttemptState, LocalStateStore, StatePhase, StateRecord

ATTEMPT_STATE_NAME = "access_attempts.json"
STATE_CATEGORY = "access_limiter"


@dataclass(frozen=True)
class AttemptDecision:
    allowed: bool
    wait_seconds: int = 0


class AttemptLimiter:
    def __init__(
        self,
        max_failures: int | None = None,
        lockout_seconds: int | None = None,
        clock=None,
    ):
        self.max_failures = max_failures or access_max_failures()
        self.lockout_seconds = lockout_seconds or access_lockout_seconds()
        self.clock = clock or time.time
        self._state: Dict[str, AttemptState] = {}

    def check(self, scope: str):
        state = self._state.get(scope, AttemptState())
        now = int(self.clock())
        if state.locked_until > now:
            return AttemptDecision(False, state.locked_until - now)
        if state.locked_until:
            # The lockout was served, so the failures that earned it are spent.
            # Without this the count survives its own penalty: after waiting the
            # full minute the caller still stands at max_failures, so the next
            # single mistake locks them out again, and again, with no way back
            # short of a success they may not be able to produce. Reported from
            # the device as the lockout "dragging on" long past its 60 seconds.
            self._forget(scope)
        return AttemptDecision(True, 0)

    def _forget(self, scope: str):
        self._state.pop(scope, None)

    def record_failure(self, scope: str):
        state = self._state.get(scope, AttemptState())
        failures = state.failures + 1
        locked_until = 0
        if failures >= self.max_failures:
            locked_until = int(self.clock()) + self.lockout_seconds
        self._state[scope] = AttemptState(failures=failures, locked_until=locked_until)

    def record_success(self, scope: str):
        self._state.pop(scope, None)


class FileAttemptLimiter(AttemptLimiter):
    def __init__(self, store: LocalStateStore | None = None, **kwargs):
        super().__init__(**kwargs)
        self.store = store or LocalStateStore()
        self._load()

    def record_failure(self, scope: str):
        super().record_failure(scope)
        self._save()

    def record_success(self, scope: str):
        super().record_success(scope)
        self._save()

    def _forget(self, scope: str):
        super()._forget(scope)
        self._save()

    def _load(self):
        record = self.store.read_record(ATTEMPT_STATE_NAME)
        if record.phase == StatePhase.CORRUPT or "attempts" not in record.attributes:
            self._state = {}
            return

        data = record.attributes["attempts"]
        self._state = {
            str(scope): AttemptState(**val)
            for scope, val in data.items()
            if isinstance(val, dict)
        }

    def _save(self):
        data = {scope: state.to_dict() for scope, state in self._state.items()}
        record = StateRecord(
            category=STATE_CATEGORY,
            phase=StatePhase.INITIALIZED,
            attributes={"attempts": data},
        )
        self.store.write_record(record, ATTEMPT_STATE_NAME)
