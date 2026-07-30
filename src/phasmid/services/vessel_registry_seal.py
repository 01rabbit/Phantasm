"""Encrypted sidecar for the Vessel registry's sensitive Face fields.

The registry serves two jobs that want opposite storage. It is the Vessel
*discovery* index, read at console start before anything is unlocked, and it is
also the per-Face bookkeeping store. Encrypting the whole file would tie
discovery to the local state key and fail closed - an empty Vessel list - on a
fresh device, a tmpfs state directory, or after a key rotation. So the file is
split: paths and fixed structural fields stay cleartext (a Vessel path is
already discoverable by looking at the filesystem), and everything that
describes or authenticates a Face's *contents* moves into this sealed sidecar.

What moves matters. Before this split, `vessel_registry.json` disclosed each
Face's file count and byte occupancy, the dummy profile identifying which Face
held generated filler, perceptual fingerprints of the bound access object, and
a scrypt verifier for that Face's destroy passphrase - in cleartext, at 0600,
readable by anyone holding the device without any passphrase and without
launching Phasmid. Those last two are credential material, and the destroy
verifier was an offline oracle for whether a passphrase offered under coercion
was the destroy one. See THREAT_MODEL.md, Configuration Directory Surface.

Sealing uses the same `LocalStateCipher` as the ORB reference blob and the
access-token store, with its own AAD for key separation.
"""

from __future__ import annotations

import json
import os

from ..config import state_dir
from ..local_state_crypto import LocalStateCipher

_SEAL_BLOB_NAME = "vessel_registry.bin"
_SEAL_KEY_NAME = "vessel_registry.key"

# Per-Face fields that describe or authenticate contents. `status` is included
# because it carries "open", which says which Face was last unlocked, and
# `label` because operator-chosen labels can be as telling as the contents.
SEALED_FACE_FIELDS = (
    "label",
    "last_accessed",
    "occupancy",
    "file_count",
    "status",
    "credentials_initialized",
    "object_binding_initialized",
    "dummy_profile",
    "object_binding",
    "emergency_auth",
)

# Vessel-level fields with the same problem. `active_face_id` names the Face
# in use, which is exactly the thing the two-Face model keeps off the visible
# path.
SEALED_RECORD_FIELDS = ("active_face_id",)

# Vessel-level fields recomputed from the Faces by the registry's normalizer
# (`_faces_to_labels`, `_aggregate_dummy_profile`), so they are dropped from
# both halves rather than stored. `dummy_profile` matters here: as an aggregate
# it still carries the plausibility level, score and file-type distribution, so
# leaving it in the cleartext half would re-disclose per-Face detail the seal
# had just removed. Nothing reads them before normalization rebuilds them.
DERIVED_RECORD_FIELDS = ("face_labels", "dummy_profile")


class VesselRegistrySeal:
    """Reads and writes the sealed half of the registry.

    Every method degrades rather than raises. A missing or undecryptable
    sidecar means "no Face detail known", not "no Vessels" - losing the state
    key must not cost an operator the ability to see and open their Vessels.
    """

    def __init__(self, state_directory: str | None = None) -> None:
        self.state_directory = state_directory or state_dir()
        self.blob_path = os.path.join(self.state_directory, _SEAL_BLOB_NAME)
        self.key_path = os.path.join(self.state_directory, _SEAL_KEY_NAME)
        self.cipher = LocalStateCipher(
            state_key_path=self.key_path,
            aad=f"phasmid-vessel-registry-v1:{_SEAL_BLOB_NAME}".encode("utf-8"),
        )

    def load(self) -> dict[str, dict[str, object]]:
        """Sealed detail keyed by resolved Vessel path.

        Returns an empty mapping when the sidecar is absent, truncated,
        authenticated under a different key, or not the JSON shape expected.
        The caller fills defaults, so a wrong key looks the same as a fresh
        device: Vessels listed, Face detail blank.
        """
        if not os.path.exists(self.blob_path):
            return {}
        try:
            with open(self.blob_path, "rb") as handle:
                payload = handle.read()
            plaintext = self.cipher.decrypt(
                payload,
                too_short_message="sealed registry blob is truncated",
                auth_failed_message="sealed registry blob failed authentication",
            )
            data = json.loads(plaintext.decode("utf-8"))
        except (OSError, ValueError, UnicodeDecodeError):
            return {}
        if not isinstance(data, dict):
            return {}
        vessels = data.get("vessels")
        if not isinstance(vessels, dict):
            return {}
        return {
            str(path): entry
            for path, entry in vessels.items()
            if isinstance(entry, dict)
        }

    def save(self, sealed: dict[str, dict[str, object]]) -> None:
        """Encrypt and write the sidecar.

        Creating the state directory here is deliberate. The registry lives in
        the config directory and is written on paths that may never have
        touched the state directory before, so the first sealed write has to be
        able to bring it into existence.
        """
        os.makedirs(self.state_directory, mode=0o700, exist_ok=True)
        plaintext = json.dumps({"vessels": sealed}, sort_keys=True).encode("utf-8")
        blob = self.cipher.encrypt(plaintext)
        with open(self.blob_path, "wb") as handle:
            handle.write(blob)
        try:
            os.chmod(self.blob_path, 0o600)
        except OSError:
            pass

    def discard(self) -> None:
        """Remove the sidecar. Used when the registry itself is emptied."""
        for path in (self.blob_path,):
            try:
                os.remove(path)
            except OSError:
                pass


def split_record(record: dict[str, object]) -> tuple[dict[str, object], dict]:
    """Divide one registry record into its cleartext and sealed halves.

    The cleartext half keeps `face_id`, `created_at` and `selector` per Face.
    Those are the fixed structural values every Vessel shares - the two-Face
    model is documented, so they disclose nothing a reader of the specification
    does not already know - and keeping them cleartext is what lets discovery
    work without the state key.
    """
    public: dict[str, object] = {
        key: value
        for key, value in record.items()
        if key not in SEALED_RECORD_FIELDS
        and key not in DERIVED_RECORD_FIELDS
        and key != "faces"
    }
    sealed_faces: dict[str, dict[str, object]] = {}
    public_faces: list[dict[str, object]] = []

    raw_faces = record.get("faces", [])
    if isinstance(raw_faces, list):
        for face in raw_faces:
            if not isinstance(face, dict):
                continue
            face_id = str(face.get("face_id", ""))
            if not face_id:
                continue
            public_faces.append(
                {
                    key: value
                    for key, value in face.items()
                    if key not in SEALED_FACE_FIELDS
                }
            )
            sealed_faces[face_id] = {
                key: face[key] for key in SEALED_FACE_FIELDS if key in face
            }

    public["faces"] = public_faces
    sealed: dict[str, object] = {"faces": sealed_faces}
    for key in SEALED_RECORD_FIELDS:
        if key in record:
            sealed[key] = record[key]
    return public, sealed


def merge_record(
    public: dict[str, object], sealed: dict[str, object] | None
) -> dict[str, object]:
    """Rebuild a full registry record from its two halves.

    Absent sealed detail leaves the sensitive keys missing rather than
    fabricating zeroes; the registry's own normalizer supplies defaults, so a
    Vessel whose detail cannot be decrypted reads as one that has never been
    written to.
    """
    merged = dict(public)
    if not isinstance(sealed, dict):
        return merged

    for key in SEALED_RECORD_FIELDS:
        if key in sealed:
            merged[key] = sealed[key]

    sealed_faces = sealed.get("faces")
    if not isinstance(sealed_faces, dict):
        return merged

    faces = merged.get("faces")
    if not isinstance(faces, list):
        return merged

    rebuilt: list[dict[str, object]] = []
    for face in faces:
        if not isinstance(face, dict):
            continue
        detail = sealed_faces.get(str(face.get("face_id", "")))
        if isinstance(detail, dict):
            face = {**face, **detail}
        rebuilt.append(face)
    merged["faces"] = rebuilt
    return merged


def record_carries_sealed_fields(record: object) -> bool:
    """Whether a cleartext record still holds fields that belong in the seal.

    True for any registry written before the split, which is what triggers
    migration on first load.
    """
    if not isinstance(record, dict):
        return False
    if any(key in record for key in SEALED_RECORD_FIELDS):
        return True
    raw_faces = record.get("faces", [])
    if not isinstance(raw_faces, list):
        return False
    return any(
        isinstance(face, dict) and any(key in face for key in SEALED_FACE_FIELDS)
        for face in raw_faces
    )
