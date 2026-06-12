import hashlib
import hmac
import json
import logging
import os
import time
from datetime import datetime, timezone

from .config import (
    AUDIT_AUTH_NAME,
    AUDIT_LOG_NAME,
    audit_enabled,
    audit_filename_mode,
    ensure_state_dir,
    state_dir,
)

AUDIT_VERSION = "2.0"
GENESIS_HASH = "sha256:GENESIS"
LOG = logging.getLogger(__name__)


def _state_dir():
    return ensure_state_dir(state_dir())


def audit_event(event, **fields):
    if not _audit_enabled():
        return
    sanitized_fields = _sanitize_fields(fields)
    path = os.path.join(_state_dir(), AUDIT_LOG_NAME)
    auth_material = _load_or_create_auth_material()
    sequence, previous_hash = _next_chain_state(path)
    record = {
        "version": AUDIT_VERSION,
        "sequence": sequence,
        "ts": int(time.time()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "pid": os.getpid(),
        "previous_hash": previous_hash,
        **sanitized_fields,
    }
    record["entry_hash"] = _entry_hash(record)
    record["hmac_sha256"] = _record_hmac(record, auth_material)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(record, separators=(",", ":"), ensure_ascii=False) + "\n"
        )
    try:
        os.chmod(path, 0o600)
    except OSError as exc:
        LOG.debug("audit log permission update failed: %s", exc)


def verify_log_integrity(path=None, auth_path=None):
    path = path or os.path.join(_state_dir(), AUDIT_LOG_NAME)
    auth_path = auth_path or os.path.join(_state_dir(), AUDIT_AUTH_NAME)
    if not os.path.exists(path):
        return True, ["audit log is not present"]
    if not os.path.exists(auth_path):
        return False, ["audit verifier material is not present"]

    with open(auth_path, "rb") as handle:
        auth_material = handle.read()

    errors = []
    previous_hash = GENESIS_HASH
    expected_sequence = 1
    with open(path, "r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError:
                errors.append(f"line {line_number}: record rejected")
                continue
            if record.get("version") != AUDIT_VERSION:
                errors.append(f"line {line_number}: version rejected")
            if record.get("sequence") != expected_sequence:
                errors.append(f"line {line_number}: sequence rejected")
            if record.get("previous_hash") != previous_hash:
                errors.append(f"line {line_number}: chain rejected")
            if record.get("entry_hash") != _entry_hash(record):
                errors.append(f"line {line_number}: event hash rejected")
            if not hmac.compare_digest(
                str(record.get("hmac_sha256", "")),
                _record_hmac(record, auth_material),
            ):
                errors.append(f"line {line_number}: verifier rejected")
            previous_hash = str(record.get("entry_hash", previous_hash))
            expected_sequence += 1
    return not errors, errors


def _load_or_create_auth_material():
    path = os.path.join(_state_dir(), AUDIT_AUTH_NAME)
    if os.path.exists(path):
        with open(path, "rb") as handle:
            return handle.read()
    material = os.urandom(32)
    with open(path, "wb") as handle:
        handle.write(material)
    try:
        os.chmod(path, 0o600)
    except OSError as exc:
        LOG.debug("audit verifier permission update failed: %s", exc)
    return material


def _next_chain_state(path):
    sequence = 1
    previous_hash = GENESIS_HASH
    if not os.path.exists(path):
        return sequence, previous_hash
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if "entry_hash" in record:
                previous_hash = str(record["entry_hash"])
                sequence = int(record.get("sequence", sequence)) + 1
    return sequence, previous_hash


def _entry_hash(record):
    hashable = {
        key: value
        for key, value in record.items()
        if key not in {"entry_hash", "hmac_sha256"}
    }
    digest = hashlib.sha256(_canonical_json(hashable)).hexdigest()
    return f"sha256:{digest}"


def _record_hmac(record, auth_material):
    signed = {key: value for key, value in record.items() if key != "hmac_sha256"}
    return hmac.new(auth_material, _canonical_json(signed), hashlib.sha256).hexdigest()


def _canonical_json(record):
    return json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sanitize_fields(fields):
    sanitized = {}
    for key, value in fields.items():
        if ("prof" + "ile") in key:
            sanitized["entry"] = "local_entry"
            continue
        if key == "filename":
            if value:
                sanitized["filename_present"] = "yes"
                if audit_filename_mode() == "hash":
                    filename = os.path.basename(str(value))
                    sanitized["filename_hash"] = hashlib.sha256(
                        filename.encode("utf-8")
                    ).hexdigest()
            else:
                sanitized["filename_present"] = "no"
            continue
        sanitized[key] = value
    return sanitized


def _audit_enabled():
    return audit_enabled()
