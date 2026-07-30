"""The Vessel registry's sensitive Face fields must not sit in cleartext.

Before the split, `vessel_registry.json` disclosed each Face's file count and
occupancy, the dummy profile identifying which Face held generated filler, the
bound object's perceptual fingerprints, and a scrypt verifier for the destroy
passphrase - readable by anyone holding the device, with no passphrase and
without launching Phasmid. See THREAT_MODEL.md, Configuration Directory
Surface.
"""

from __future__ import annotations

import contextlib
import importlib
import json
import os
import tempfile
from unittest import mock

import pytest


@contextlib.contextmanager
def isolated_dirs():
    """Fresh config and state directories, with the module caches reset.

    `vessel_service` resolves the registry path through `config_dir()` on every
    call, but `profile_service` and `config` are imported at module scope, so
    the modules are reloaded to make sure nothing carries over between cases.
    """
    with tempfile.TemporaryDirectory() as tmp:
        config = os.path.join(tmp, "config")
        state = os.path.join(tmp, "state")
        os.makedirs(config, mode=0o700, exist_ok=True)
        os.makedirs(state, mode=0o700, exist_ok=True)
        with mock.patch.dict(
            os.environ,
            {"PHASMID_CONFIG_DIR": config, "PHASMID_STATE_DIR": state},
            clear=False,
        ):
            import phasmid.services.vessel_registry_seal as seal_mod
            import phasmid.services.vessel_service as vs

            importlib.reload(seal_mod)
            importlib.reload(vs)
            yield vs, seal_mod, config, state


def _cleartext(config_dir: str) -> dict:
    with open(os.path.join(config_dir, "vessel_registry.json"), encoding="utf-8") as fh:
        return json.load(fh)


def _face_detail() -> dict:
    """One fully populated Face, as a real store-plus-bind flow would leave it."""
    return {
        "face_id": "face_a",
        "label": "travel",
        "created_at": "2026-07-30T00:00:00+00:00",
        "last_accessed": "2026-07-30T01:00:00+00:00",
        "occupancy": 4096,
        "file_count": 12,
        "status": "open",
        "selector": "a",
        "credentials_initialized": True,
        "object_binding_initialized": True,
        "dummy_profile": {
            "dummy_file_count": 7,
            "dummy_total_size": 2048,
            "occupancy_ratio": 0.15,
            "file_type_distribution": {"txt": 7},
            "plausibility_score": 80,
            "plausibility_level": "HIGH",
            "last_updated_at": "2026-07-30T01:00:00+00:00",
        },
        "object_binding": {
            "source_type": "camera",
            "average_hash": "ffff0000ffff0000",
            "edge_hash": "0f0f0f0f0f0f0f0f",
            "brightness_histogram": [0.1, 0.2],
            "color_histogram": [0.3, 0.4],
            "threshold": 0.82,
            "fingerprint_id": "fp-1",
            "updated_at": "2026-07-30T01:00:00+00:00",
        },
        "emergency_auth": {
            "salt_b64": "c2FsdHNhbHRzYWx0c2E9",
            "hash_b64": "aGFzaGhhc2hoYXNoaGE9",
            "updated_at": "2026-07-30T01:00:00+00:00",
            "kdf_n": 32768,
            "kdf_r": 8,
            "kdf_p": 1,
        },
    }


def test_sealed_fields_round_trip_through_save_and_load():
    with isolated_dirs() as (vs, _seal, _config, _state):
        vessel = "/tmp/demo.vessel"
        vs.register_vessel(vessel)
        vs.update_face_access(
            vessel,
            "face_a",
            occupancy=4096,
            file_count=12,
            object_binding=_face_detail()["object_binding"],
            emergency_auth=_face_detail()["emergency_auth"],
            dummy_profile=_face_detail()["dummy_profile"],
            credentials_initialized=True,
        )

        record = vs.get_vessel_record(vessel)
        assert record is not None
        face = next(f for f in record["faces"] if f["face_id"] == "face_a")
        assert face["file_count"] == 12
        assert face["occupancy"] == 4096
        assert face["credentials_initialized"] is True
        assert face["object_binding"]["average_hash"] == "ffff0000ffff0000"
        assert face["emergency_auth"]["hash_b64"] == "aGFzaGhhc2hoYXNoaGE9"
        assert face["dummy_profile"]["plausibility_level"] == "HIGH"


@pytest.mark.parametrize(
    "sealed_key",
    ["object_binding", "emergency_auth", "dummy_profile", "file_count", "occupancy"],
)
def test_cleartext_registry_never_holds_sealed_fields(sealed_key):
    """The whole point: none of this may survive in the cleartext index."""
    with isolated_dirs() as (vs, _seal, config, _state):
        vessel = "/tmp/demo.vessel"
        vs.register_vessel(vessel)
        vs.update_face_access(
            vessel,
            "face_a",
            occupancy=4096,
            file_count=12,
            object_binding=_face_detail()["object_binding"],
            emergency_auth=_face_detail()["emergency_auth"],
            dummy_profile=_face_detail()["dummy_profile"],
            credentials_initialized=True,
        )

        raw = _cleartext(config)
        blob = json.dumps(raw)
        for entry in raw["vessels"]:
            for face in entry.get("faces", []):
                assert sealed_key not in face

        # And no stray copy anywhere in the file, including the aggregate the
        # record used to carry alongside the per-Face figures.
        if sealed_key in ("object_binding", "emergency_auth", "dummy_profile"):
            assert sealed_key not in blob
        assert "ffff0000ffff0000" not in blob, "object fingerprint left in cleartext"
        assert "aGFzaGhhc2hoYXNoaGE9" not in blob, "destroy verifier left in cleartext"
        assert "travel" not in blob, "Face label left in cleartext"


def test_vessels_stay_listable_when_the_sidecar_is_missing():
    """Losing the state key must cost Face detail, never Vessel access."""
    with isolated_dirs() as (vs, seal, _config, _state):
        vessel = "/tmp/demo.vessel"
        vs.register_vessel(vessel)
        vs.update_face_access(vessel, "face_a", file_count=12, occupancy=4096)

        os.remove(seal.VesselRegistrySeal().blob_path)

        record = vs.get_vessel_record(vessel)
        assert record is not None
        assert record["path"] == vessel
        face = next(f for f in record["faces"] if f["face_id"] == "face_a")
        assert face["file_count"] == 0
        assert face["occupancy"] == 0
        assert face["credentials_initialized"] is False


def test_a_sidecar_under_the_wrong_key_degrades_instead_of_raising():
    with isolated_dirs() as (vs, seal, _config, state):
        vessel = "/tmp/demo.vessel"
        vs.register_vessel(vessel)
        vs.update_face_access(vessel, "face_a", file_count=12)

        # Rotating the key leaves an authentic-looking blob that will not
        # authenticate - the same situation as a restored backup.
        with open(os.path.join(state, "vessel_registry.key"), "wb") as fh:
            fh.write(os.urandom(32))

        assert seal.VesselRegistrySeal().load() == {}
        record = vs.get_vessel_record(vessel)
        assert record is not None
        face = next(f for f in record["faces"] if f["face_id"] == "face_a")
        assert face["file_count"] == 0


def test_a_truncated_sidecar_degrades_instead_of_raising():
    with isolated_dirs() as (vs, seal, _config, _state):
        vessel = "/tmp/demo.vessel"
        vs.register_vessel(vessel)
        vs.update_face_access(vessel, "face_a", file_count=12)

        with open(seal.VesselRegistrySeal().blob_path, "wb") as fh:
            fh.write(b"\x00\x01\x02")

        assert seal.VesselRegistrySeal().load() == {}
        assert vs.get_vessel_record(vessel) is not None


def test_a_legacy_plaintext_registry_is_migrated_on_first_load():
    """The pre-split file is the only copy, so it must be read, then sealed."""
    with isolated_dirs() as (vs, seal, config, _state):
        vessel = "/tmp/legacy.vessel"
        legacy = {
            "vessels": [
                {
                    "path": vessel,
                    "label": "",
                    "faces": [_face_detail()],
                    "is_open": False,
                    "open_count": 3,
                    "active_face_id": "face_a",
                }
            ]
        }
        registry = os.path.join(config, "vessel_registry.json")
        with open(registry, "w", encoding="utf-8") as fh:
            json.dump(legacy, fh)

        # The values survive the move.
        record = vs.get_vessel_record(vessel)
        assert record is not None
        face = next(f for f in record["faces"] if f["face_id"] == "face_a")
        assert face["file_count"] == 12
        assert face["object_binding"]["average_hash"] == "ffff0000ffff0000"
        assert face["emergency_auth"]["kdf_n"] == 32768
        assert record["active_face_id"] == "face_a"
        assert record["open_count"] == 3

        # And they are gone from the cleartext file, which was shredded rather
        # than merely rewritten.
        blob = json.dumps(_cleartext(config))
        assert "ffff0000ffff0000" not in blob
        assert "aGFzaGhhc2hoYXNoaGE9" not in blob
        assert "active_face_id" not in blob
        assert os.path.exists(seal.VesselRegistrySeal().blob_path)


def test_a_purged_face_is_indistinguishable_from_an_unused_one_without_the_key():
    """Otherwise destruction is detectable from local state after a purge.

    `forget_face_contents` deliberately keeps `object_binding` and
    `emergency_auth` as credentials, so before the split a purged Face stayed
    identifiable as bound-and-credentialed-with-zero-files while a never-used
    Face was unbound and uncredentialed. That difference told a reader that
    data had been destroyed - the legal exposure of the duress path without the
    deniability it exists for.
    """
    with isolated_dirs() as (vs, _seal, config, _state):
        used = "/tmp/used.vessel"
        untouched = "/tmp/untouched.vessel"
        vs.register_vessel(used)
        vs.register_vessel(untouched)

        vs.update_face_access(
            used,
            "face_a",
            occupancy=4096,
            file_count=12,
            credentials_initialized=True,
            object_binding_initialized=True,
            object_binding=_face_detail()["object_binding"],
            emergency_auth=_face_detail()["emergency_auth"],
        )
        # Now purge it the way the destroy path does.
        vs.update_face_access(
            used, "face_a", occupancy=0, file_count=0, status="available"
        )

        raw = _cleartext(config)
        by_path = {entry["path"]: entry for entry in raw["vessels"]}

        def faces(path):
            return sorted(
                (
                    {key: value for key, value in face.items()}
                    for face in by_path[path]["faces"]
                ),
                key=lambda face: face["face_id"],
            )

        purged = faces(used)
        never_used = faces(untouched)
        # created_at is stamped per registration, so compare the fields that
        # would otherwise carry the tell.
        assert len(purged) == len(never_used)
        for left, right in zip(purged, never_used, strict=True):
            assert set(left) == set(right)
            assert left["face_id"] == right["face_id"]
            assert left["selector"] == right["selector"]


def test_emptying_the_registry_discards_the_sidecar():
    with isolated_dirs() as (vs, seal, _config, _state):
        vessel = "/tmp/demo.vessel"
        vs.register_vessel(vessel)
        vs.update_face_access(vessel, "face_a", file_count=12)
        assert os.path.exists(seal.VesselRegistrySeal().blob_path)

        assert vs.unregister_vessel(vessel) is True
        assert not os.path.exists(seal.VesselRegistrySeal().blob_path)


def test_the_sidecar_is_owner_only():
    with isolated_dirs() as (vs, seal, _config, _state):
        vs.register_vessel("/tmp/demo.vessel")
        mode = os.stat(seal.VesselRegistrySeal().blob_path).st_mode & 0o777
        assert mode == 0o600


def test_destroy_verifier_uses_the_argon2_memory_tier():
    """The verifier has to exist, so its cost is what protects it.

    `destroy_face` and `destroy_vessel` authenticate against this hash rather
    than by opening the container, because they overwrite raw bytes and must
    work on a container that cannot be decrypted. It previously used the
    interactive-login tier (n=2**14).
    """
    from phasmid import crypto_params

    assert crypto_params.SCRYPT_DESTROY_N == 2**15
    # 128 * r * n, matching ARGON2_MEMORY_COST (KiB -> bytes).
    assert (
        128 * crypto_params.SCRYPT_DESTROY_R * crypto_params.SCRYPT_DESTROY_N
        == crypto_params.ARGON2_MEMORY_COST * 1024
    )
    assert crypto_params.SCRYPT_DESTROY_MAXMEM > (
        128 * crypto_params.SCRYPT_DESTROY_R * crypto_params.SCRYPT_DESTROY_N
    )


def test_a_destroy_passphrase_set_under_legacy_parameters_still_verifies():
    """Raising the cost must not lock an operator out of their own destroy path."""
    import base64
    import hashlib

    from phasmid import crypto_params
    from phasmid.services.vessel_workflow_service import VesselWorkflowService

    salt = b"sixteen-byte-salt"
    digest = hashlib.scrypt(
        b"destroy-me-please",
        salt=salt,
        n=crypto_params.SCRYPT_DESTROY_LEGACY_N,
        r=crypto_params.SCRYPT_DESTROY_LEGACY_R,
        p=crypto_params.SCRYPT_DESTROY_LEGACY_P,
        dklen=32,
    )
    legacy_record = {
        "salt_b64": base64.b64encode(salt).decode("ascii"),
        "hash_b64": base64.b64encode(digest).decode("ascii"),
        # No kdf_* keys, exactly as records written before they were recorded.
    }

    svc = VesselWorkflowService.__new__(VesselWorkflowService)
    with mock.patch.object(
        VesselWorkflowService,
        "_get_face_emergency_auth_record",
        lambda self, path, face_id: legacy_record,
    ):
        assert (
            svc._verify_face_emergency_password(
                "/tmp/x.vessel", "face_a", "destroy-me-please"
            )
            is True
        )
        assert (
            svc._verify_face_emergency_password("/tmp/x.vessel", "face_a", "wrong")
            is False
        )


def test_unusable_recorded_kdf_parameters_do_not_read_as_a_match():
    from phasmid.services.vessel_workflow_service import VesselWorkflowService

    broken = {
        "salt_b64": "c2FsdA==",
        "hash_b64": "aGFzaA==",
        "kdf_n": 3,  # not a power of two; scrypt rejects it
        "kdf_r": 8,
        "kdf_p": 1,
    }
    svc = VesselWorkflowService.__new__(VesselWorkflowService)
    with mock.patch.object(
        VesselWorkflowService,
        "_get_face_emergency_auth_record",
        lambda self, path, face_id: broken,
    ):
        assert (
            svc._verify_face_emergency_password("/tmp/x.vessel", "face_a", "anything")
            is False
        )
