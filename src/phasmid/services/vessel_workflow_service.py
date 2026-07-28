from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from ..attempt_limiter import FileAttemptLimiter
from ..models.vessel import DummyProfileMeta, FaceMeta, VesselMeta
from ..vault_core import PhasmidVault
from .access_cue_service import access_cue_service
from .object_binding_service import ObjectBindingProfile, ObjectBindingService
from .vessel_service import VesselService

_SIZE_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([a-zA-Z]+)?\s*$")
_SIZE_SUFFIXES = {
    "m": 1024 * 1024,
    "mb": 1024 * 1024,
    "mib": 1024 * 1024,
    "g": 1024 * 1024 * 1024,
    "gb": 1024 * 1024 * 1024,
    "gib": 1024 * 1024 * 1024,
}
_ENTRY_TO_MODE = {
    "a": "dummy",
    "b": "secret",
    "face_a": "dummy",
    "face_b": "secret",
    "face_1": "dummy",
    "face_2": "secret",
    "profile_a": "dummy",
    "profile_b": "secret",
    "dummy": "dummy",
    "secret": "secret",
}
_FACE_ALIASES = {
    "a": "face_a",
    "b": "face_b",
    "face_a": "face_a",
    "face_b": "face_b",
    "face_1": "face_a",
    "face_2": "face_b",
    "dummy": "face_a",
    "secret": "face_b",
}
_FACE_NAMESPACE_MARKER = "phasmid-face-namespace-v1"
_GENERATED_PLAUSIBILITY_ORIGIN = "generated_plausibility"
_PLAUSIBILITY_EXTENSIONS = ("txt", "md", "pdf", "csv", "jpg")


@dataclass(frozen=True)
class CreateVesselResult:
    vessel_path: Path
    size_bytes: int


@dataclass(frozen=True)
class StorePayloadResult:
    vessel_path: Path
    input_path: Path
    bytes_stored: int
    mode: str


@dataclass(frozen=True)
class RetrievePayloadResult:
    vessel_path: Path
    output_path: Path | None
    bytes_retrieved: int
    filename: str | None
    mode: str
    password_role: str | None


@dataclass(frozen=True)
class OpenVesselResult:
    vessel: VesselMeta


@dataclass(frozen=True)
class CloseVesselResult:
    vessel: VesselMeta


@dataclass(frozen=True)
class FaceResult:
    vessel: VesselMeta
    face: FaceMeta


@dataclass(frozen=True)
class FaceFileRecord:
    name: str
    size: int
    added_at: str


@dataclass(frozen=True)
class FaceFileListResult:
    vessel: VesselMeta
    face: FaceMeta
    files: list[FaceFileRecord]


@dataclass(frozen=True)
class DummyProfileResult:
    vessel: VesselMeta
    face: FaceMeta
    profile: DummyProfileMeta
    recommended_action: str


@dataclass(frozen=True)
class EmergencyDestroyResult:
    vessel_path: Path
    face_id: str | None
    scope: str


class VesselWorkflowService:
    def __init__(self) -> None:
        self._vessels = VesselService()
        self._access_cue = access_cue_service
        self._object_binding = ObjectBindingService()

    def resolve_mode(self, selector: str | None) -> str:
        key = (selector or "a").strip().lower()
        if key not in _ENTRY_TO_MODE:
            raise ValueError("unsupported disclosure face selector")
        return _ENTRY_TO_MODE[key]

    def resolve_face_id(self, selector: str | None) -> str:
        key = (selector or "face_a").strip().lower()
        if key not in _FACE_ALIASES:
            raise ValueError("unsupported face selector")
        return _FACE_ALIASES[key]

    def parse_size_spec(self, size_spec: str) -> tuple[int, float]:
        match = _SIZE_RE.match(size_spec)
        if match is None:
            raise ValueError("size must look like 512M, 1G, 512MiB, or 1GiB")

        value = float(match.group(1))
        suffix = (match.group(2) or "mib").lower()
        if suffix not in _SIZE_SUFFIXES:
            raise ValueError("size unit must be M, MiB, G, or GiB")

        size_bytes = int(value * _SIZE_SUFFIXES[suffix])
        if size_bytes < PhasmidVault.MIN_CONTAINER_SIZE:
            raise ValueError(
                f"container size must be at least {PhasmidVault.MIN_CONTAINER_SIZE} bytes"
            )
        return size_bytes, size_bytes / (1024 * 1024)

    def parse_storage_size_spec(self, size_spec: str) -> int:
        match = _SIZE_RE.match(size_spec)
        if match is None:
            raise ValueError("size must look like 16M, 64M, 1G, 16MiB, or 1GiB")

        value = float(match.group(1))
        suffix = (match.group(2) or "mib").lower()
        if suffix not in _SIZE_SUFFIXES:
            raise ValueError("size unit must be M, MiB, G, or GiB")
        return max(0, int(value * _SIZE_SUFFIXES[suffix]))

    def parse_occupancy_spec(self, occupancy_spec: str) -> float:
        value = occupancy_spec.strip()
        if value.endswith("%"):
            ratio = float(value[:-1]) / 100.0
        else:
            ratio = float(value)
            if ratio > 1.0:
                ratio /= 100.0
        if ratio < 0.0 or ratio > 1.0:
            raise ValueError("target occupancy must be between 0% and 100%")
        return ratio

    def create_vessel(
        self,
        path: str | Path,
        size_spec: str,
        overwrite: bool = False,
        label: str = "",
    ) -> CreateVesselResult:
        vessel_path = Path(path).expanduser().resolve()
        size_bytes, size_mb = self.parse_size_spec(size_spec)
        if vessel_path.exists() and not overwrite:
            raise FileExistsError(f"vessel already exists: {vessel_path}")

        vessel_path.parent.mkdir(parents=True, exist_ok=True)
        vault = PhasmidVault(str(vessel_path), size_mb=size_mb)
        vault.format_container(rotate_access_key=True)
        self._vessels.register(vessel_path)
        if label:
            self._vessels.set_metadata(vessel_path, label=label)
        return CreateVesselResult(vessel_path=vessel_path, size_bytes=size_bytes)

    def create_face(
        self,
        path: str | Path,
        face_id: str,
        label: str = "",
    ) -> FaceResult:
        vessel_path = Path(path).expanduser().resolve()
        if not vessel_path.exists():
            raise FileNotFoundError(f"vessel file not found: {vessel_path}")
        resolved_face_id = self.resolve_face_id(face_id)
        default_label = (
            "Disclosure Face 1" if resolved_face_id == "face_a" else "Disclosure Face 2"
        )
        selector = "a" if resolved_face_id == "face_a" else "b"
        self._vessels.create_face(
            vessel_path, resolved_face_id, label or default_label, selector
        )
        vessel = self._get_meta(vessel_path)
        face = self._get_face(vessel, resolved_face_id)
        return FaceResult(vessel=vessel, face=face)

    def open_vessel(
        self, path: str | Path, face_id: str = "face_a"
    ) -> OpenVesselResult:
        vessel_path = Path(path).expanduser().resolve()
        if not vessel_path.exists():
            raise FileNotFoundError(f"vessel file not found: {vessel_path}")
        self._vessels.open_face(vessel_path, self.resolve_face_id(face_id))
        return OpenVesselResult(vessel=self._get_meta(vessel_path))

    def close_vessel(self, path: str | Path) -> CloseVesselResult:
        vessel_path = Path(path).expanduser().resolve()
        record = self._vessels.get_record(vessel_path)
        if record is None:
            raise FileNotFoundError(f"vessel is not registered: {vessel_path}")
        self._vessels.close(vessel_path)
        return CloseVesselResult(vessel=self._get_meta(vessel_path))

    def _get_meta(self, path: Path) -> VesselMeta:
        for vessel in self._vessels.list_all():
            if vessel.path.resolve() == path.resolve():
                return vessel
        raise FileNotFoundError(f"vessel file not found: {path}")

    def _get_face(self, vessel: VesselMeta, face_id: str) -> FaceMeta:
        for face in vessel.faces:
            if face.face_id == face_id:
                return face
        raise ValueError(f"unsupported face id: {face_id}")

    def _get_face_binding_record(
        self, path: str | Path, face_id: str
    ) -> dict[str, object]:
        record = self._vessels.get_record(path)
        if not record:
            return {}
        for face in cast(list[dict[str, object]], record.get("faces", [])):
            if str(face.get("face_id", "")) == face_id:
                return self._object_binding.normalize_record(
                    face.get("object_binding", {})
                )
        return {}

    def _get_face_state_record(
        self, path: str | Path, face_id: str
    ) -> dict[str, object]:
        record = self._vessels.get_record(path)
        if not record:
            return {}
        for face in cast(list[dict[str, object]], record.get("faces", [])):
            if str(face.get("face_id", "")) == face_id:
                return face
        return {}

    def _get_face_emergency_auth_record(
        self, path: str | Path, face_id: str
    ) -> dict[str, object]:
        record = self._vessels.get_record(path)
        if not record:
            return {}
        for face in cast(list[dict[str, object]], record.get("faces", [])):
            if str(face.get("face_id", "")) == face_id:
                auth = face.get("emergency_auth", {})
                if isinstance(auth, dict):
                    return auth
        return {}

    def _set_face_binding_record(
        self,
        path: str | Path,
        face_id: str,
        binding_record: dict[str, object],
    ) -> None:
        self._vessels.touch_face(
            path,
            face_id,
            object_binding=self._object_binding.normalize_record(binding_record),
            object_binding_initialized=True,
        )

    def _set_face_emergency_password(
        self,
        path: str | Path,
        face_id: str,
        emergency_password: str,
    ) -> None:
        salt = os.urandom(16)
        digest = hashlib.scrypt(
            emergency_password.encode("utf-8"),
            salt=salt,
            n=2**14,
            r=8,
            p=1,
            dklen=32,
        )
        self._vessels.touch_face(
            path,
            face_id,
            emergency_auth={
                "salt_b64": base64.b64encode(salt).decode("ascii"),
                "hash_b64": base64.b64encode(digest).decode("ascii"),
                "updated_at": self._current_timestamp(),
            },
        )

    def _verify_face_emergency_password(
        self,
        path: str | Path,
        face_id: str,
        emergency_password: str,
    ) -> bool:
        record = self._get_face_emergency_auth_record(path, face_id)
        salt_b64 = str(record.get("salt_b64", ""))
        hash_b64 = str(record.get("hash_b64", ""))
        if not salt_b64 or not hash_b64:
            return False
        salt = base64.b64decode(salt_b64.encode("ascii"))
        expected = base64.b64decode(hash_b64.encode("ascii"))
        actual = hashlib.scrypt(
            emergency_password.encode("utf-8"),
            salt=salt,
            n=2**14,
            r=8,
            p=1,
            dklen=len(expected),
        )
        return actual == expected

    def _binding_registered(self, binding_record: dict[str, object]) -> bool:
        return bool(binding_record.get("source_type"))

    def _credentials_initialized(self, path: str | Path, face_id: str) -> bool:
        face = self._get_face_state_record(path, face_id)
        return bool(face.get("credentials_initialized", False))

    def face_requires_initialization(
        self, path: str | Path, selector: str = "face_a"
    ) -> bool:
        return not self._credentials_initialized(
            Path(path).expanduser().resolve(),
            self.resolve_face_id(selector),
        )

    def _capture_camera_profile(self) -> ObjectBindingProfile:
        frame = self._access_cue.latest_frame_copy()
        if frame is None:
            raise RuntimeError("object source unavailable: camera frame not available")
        return self._object_binding.profile_from_frame(frame)

    def _candidate_binding_profile(
        self,
        *,
        object_image_path: str | None = None,
        camera_object: bool = False,
        no_object_binding: bool = False,
    ) -> ObjectBindingProfile | dict[str, object] | None:
        if no_object_binding:
            if not self._object_binding.no_object_binding_allowed():
                raise ValueError(
                    "no-object-binding is restricted to local development tests"
                )
            return self._object_binding.disabled_record()
        if object_image_path:
            return self._object_binding.profile_from_image_path(object_image_path)
        if camera_object:
            return self._capture_camera_profile()
        return None

    def _ensure_object_binding(
        self,
        vessel_path: Path,
        selector: str,
        *,
        object_image_path: str | None = None,
        camera_object: bool = False,
        no_object_binding: bool = False,
        register_if_missing: bool = False,
    ) -> list[str] | None:
        face_id = self.resolve_face_id(selector)
        binding_record = self._get_face_binding_record(vessel_path, face_id)
        candidate = self._candidate_binding_profile(
            object_image_path=object_image_path,
            camera_object=camera_object,
            no_object_binding=no_object_binding,
        )

        if not self._binding_registered(binding_record):
            if candidate is None:
                return None
            if not register_if_missing:
                raise ValueError("object binding not registered for selected face")
            if isinstance(candidate, dict):
                self._set_face_binding_record(vessel_path, face_id, candidate)
            else:
                self._set_face_binding_record(
                    vessel_path, face_id, candidate.to_record()
                )
            return cast(
                list[str],
                self._access_cue.sequence_for_mode(self.resolve_mode(selector)),
            )

        source_type = str(binding_record.get("source_type", ""))
        if source_type == "disabled":
            if not no_object_binding:
                raise ValueError("object mismatch")
            return cast(
                list[str],
                self._access_cue.sequence_for_mode(self.resolve_mode(selector)),
            )

        if candidate is None:
            candidate = self._capture_camera_profile()
        if isinstance(candidate, dict):
            raise ValueError("object mismatch")

        match = self._object_binding.match(
            binding_record,
            candidate,
            tolerant=camera_object or not object_image_path,
        )
        if not match.matched:
            raise ValueError("object mismatch")
        return cast(
            list[str],
            self._access_cue.sequence_for_mode(self.resolve_mode(selector)),
        )

    def _empty_namespace(self) -> dict[str, object]:
        return {"format": _FACE_NAMESPACE_MARKER, "files": {}}

    def _decode_namespace(self, data: bytes, filename: str | None) -> dict[str, object]:
        try:
            payload = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = None
        if (
            isinstance(payload, dict)
            and payload.get("format") == _FACE_NAMESPACE_MARKER
            and isinstance(payload.get("files"), dict)
        ):
            return payload
        legacy_name = filename or "payload.bin"
        return {
            "format": _FACE_NAMESPACE_MARKER,
            "files": {
                legacy_name: {
                    "data_b64": base64.b64encode(data).decode("ascii"),
                    "size": len(data),
                    "added_at": "",
                }
            },
        }

    def _encode_namespace(self, namespace: dict[str, object]) -> tuple[bytes, str]:
        return (
            json.dumps(namespace, separators=(",", ":"), ensure_ascii=False).encode(
                "utf-8"
            ),
            "face-namespace.bin",
        )

    def _namespace_file_records(
        self, namespace: dict[str, object]
    ) -> list[FaceFileRecord]:
        files = namespace.get("files", {})
        if not isinstance(files, dict):
            return []
        records: list[FaceFileRecord] = []
        for name, item in files.items():
            if not isinstance(item, dict):
                continue
            records.append(
                FaceFileRecord(
                    name=str(name),
                    size=int(item.get("size", 0)),
                    added_at=str(item.get("added_at", "")),
                )
            )
        return sorted(records, key=lambda record: record.name)

    def _current_timestamp(self) -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def _generated_entry(self, filename: str, payload: bytes) -> dict[str, object]:
        return {
            "data_b64": base64.b64encode(payload).decode("ascii"),
            "size": len(payload),
            "added_at": self._current_timestamp(),
            "origin": _GENERATED_PLAUSIBILITY_ORIGIN,
        }

    def _text_payload(self, title: str, approx_size: int) -> bytes:
        lines = [
            f"{title}\n",
            "Status: nominal.\n",
            "Reference: local working copy.\n",
            "Prepared for offline review.\n",
        ]
        content = "".join(lines)
        while len(content.encode("utf-8")) < approx_size:
            content += "Checklist item reviewed and archived.\n"
        return content.encode("utf-8")[:approx_size]

    def _csv_payload(self, approx_size: int) -> bytes:
        rows = ["id,name,status,value\n"]
        idx = 1
        while len("".join(rows).encode("utf-8")) < approx_size:
            rows.append(f"{idx},item_{idx:03d},active,{idx * 7}\n")
            idx += 1
        return "".join(rows).encode("utf-8")[:approx_size]

    def _pdf_payload(self, title: str, approx_size: int) -> bytes:
        body = (
            "%PDF-1.1\n"
            "1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            "2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
            "3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 144]"
            "/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj\n"
        )
        text = (title + " local review copy").replace("(", "[").replace(")", "]")
        stream = f"BT /F1 12 Tf 36 96 Td ({text}) Tj ET"
        content = (
            body
            + f"4 0 obj<</Length {len(stream)}>>stream\n{stream}\nendstream endobj\n"
            + "5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
            + "xref\n0 6\n0000000000 65535 f \n"
            + "trailer<</Root 1 0 R/Size 6>>\nstartxref\n0\n%%EOF\n"
        ).encode("utf-8")
        if len(content) >= approx_size:
            return content[:approx_size]
        return content + b"\n" + b"%" * max(0, approx_size - len(content) - 1)

    def _jpg_payload(self, approx_size: int) -> bytes:
        header = bytes.fromhex("FFD8FFE000104A46494600010100000100010000")
        footer = bytes.fromhex("FFD9")
        middle = b"\x00" * max(0, approx_size - len(header) - len(footer))
        return (header + middle + footer)[:approx_size]

    def _build_generated_file_specs(self, target_bytes: int) -> list[tuple[str, bytes]]:
        if target_bytes <= 0:
            return []

        specs = [
            (
                "field_notes_01.txt",
                self._text_payload("Field Notes", max(256, target_bytes // 10)),
            ),
            (
                "briefing_01.md",
                self._text_payload("# Briefing", max(320, target_bytes // 12)),
            ),
            (
                "report_01.pdf",
                self._pdf_payload("Operational Report", max(768, target_bytes // 8)),
            ),
            ("logsheet_01.csv", self._csv_payload(max(256, target_bytes // 12))),
            ("site_photo_01.jpg", self._jpg_payload(max(512, target_bytes // 10))),
        ]
        total = sum(len(payload) for _name, payload in specs)
        idx = 2
        while total < target_bytes:
            ext = _PLAUSIBILITY_EXTENSIONS[(idx - 2) % len(_PLAUSIBILITY_EXTENSIONS)]
            remaining = target_bytes - total
            approx_size = min(
                max(192, target_bytes // (8 + idx)),
                max(192, remaining),
            )
            if ext == "txt":
                payload = self._text_payload(f"Notes {idx}", approx_size)
            elif ext == "md":
                payload = self._text_payload(f"# Summary {idx}", approx_size)
            elif ext == "pdf":
                payload = self._pdf_payload(f"Report {idx}", approx_size)
            elif ext == "csv":
                payload = self._csv_payload(approx_size)
            else:
                payload = self._jpg_payload(approx_size)
            specs.append((f"generated_{idx:02d}.{ext}", payload))
            total += len(payload)
            idx += 1
        return specs

    def _bucket_counts(self, sizes: list[int]) -> int:
        buckets: set[str] = set()
        for size in sizes:
            if size < 4 * 1024:
                buckets.add("tiny")
            elif size < 64 * 1024:
                buckets.add("small")
            elif size < 256 * 1024:
                buckets.add("medium")
            else:
                buckets.add("large")
        return len(buckets)

    def _build_dummy_profile(
        self,
        vessel_path: Path,
        namespace: dict[str, object],
    ) -> dict[str, object]:
        files = namespace.get("files", {})
        if not isinstance(files, dict):
            return {
                "dummy_file_count": 0,
                "dummy_total_size": 0,
                "occupancy_ratio": 0.0,
                "file_type_distribution": {},
                "plausibility_score": 0,
                "plausibility_level": "LOW",
                "last_updated_at": self._current_timestamp(),
            }

        generated: list[tuple[str, dict[str, object]]] = []
        for name, item in files.items():
            if not isinstance(item, dict):
                continue
            if str(item.get("origin", "")) != _GENERATED_PLAUSIBILITY_ORIGIN:
                continue
            generated.append((str(name), item))

        dummy_file_count = len(generated)
        dummy_total_size = sum(
            int(cast(int, item.get("size", 0))) for _name, item in generated
        )
        vessel_size = max(1, vessel_path.stat().st_size)
        occupancy_ratio = dummy_total_size / float(vessel_size)

        distribution: dict[str, int] = {}
        sizes: list[int] = []
        for name, item in generated:
            ext = Path(name).suffix.lower().lstrip(".") or "bin"
            distribution[ext] = distribution.get(ext, 0) + 1
            sizes.append(int(cast(int, item.get("size", 0))))

        unique_ext = len(distribution)
        occupied_score = min(30, int(min(occupancy_ratio, 0.20) / 0.20 * 30))
        file_count_score = min(25, dummy_file_count * 2)
        diversity_score = min(20, unique_ext * 4)
        size_distribution_score = min(15, self._bucket_counts(sizes) * 5)
        unique_size_ratio = (len(set(sizes)) / len(sizes)) if sizes else 0.0
        uniformity_score = min(10, int(unique_size_ratio * 10))
        plausibility_score = min(
            100,
            occupied_score
            + file_count_score
            + diversity_score
            + size_distribution_score
            + uniformity_score,
        )
        if plausibility_score >= 70:
            plausibility_level = "HIGH"
        elif plausibility_score >= 40:
            plausibility_level = "MEDIUM"
        else:
            plausibility_level = "LOW"

        return {
            "dummy_file_count": dummy_file_count,
            "dummy_total_size": dummy_total_size,
            "occupancy_ratio": occupancy_ratio,
            "file_type_distribution": distribution,
            "plausibility_score": plausibility_score,
            "plausibility_level": plausibility_level,
            "last_updated_at": self._current_timestamp(),
        }

    def _recommended_action(self, profile: DummyProfileMeta) -> str:
        if profile.plausibility_level == "HIGH":
            return "Baseline profile is credible. Periodically refresh file mix."
        if profile.plausibility_level == "MEDIUM":
            return (
                "Add more size variation or increase occupancy for a stronger baseline."
            )
        return "Generate a broader local baseline before field use."

    def _read_face_namespace(
        self,
        vessel_path: Path,
        open_passphrase: str,
        selector: str,
        cue_sequence: list[str],
    ) -> tuple[dict[str, object], str | None]:
        # Deliberately open-slot only. The restricted recovery passphrase is a
        # destroy credential in this layer, not a retrieval one, and
        # test_emergency_password_does_not_trigger_normal_list_or_retrieve
        # pins that: reading with it must fail rather than disclose.
        mode = self.resolve_mode(selector)
        face_id = self.resolve_face_id(selector)
        vault = PhasmidVault(
            str(vessel_path), size_mb=vessel_path.stat().st_size / (1024 * 1024)
        )
        data, filename = vault.retrieve_open_only(
            open_passphrase,
            cue_sequence,
            mode=mode,
        )
        if data is None:
            if not self._credentials_initialized(vessel_path, face_id):
                return self._empty_namespace(), None
            raise ValueError("password mismatch")
        return self._decode_namespace(data, filename), filename

    def _write_face_namespace(
        self,
        vessel_path: Path,
        open_passphrase: str,
        restricted_passphrase: str | None,
        selector: str,
        cue_sequence: list[str],
        namespace: dict[str, object],
    ) -> None:
        mode = self.resolve_mode(selector)
        encoded, filename = self._encode_namespace(namespace)
        vault = PhasmidVault(
            str(vessel_path), size_mb=vessel_path.stat().st_size / (1024 * 1024)
        )
        if restricted_passphrase is None:
            vault.store_open_only(
                open_passphrase,
                encoded,
                cue_sequence,
                filename=filename,
                mode=mode,
            )
        else:
            vault.store(
                open_passphrase,
                encoded,
                cue_sequence,
                filename=filename,
                mode=mode,
                restricted_recovery_password=restricted_passphrase,
            )
        files = self._namespace_file_records(namespace)
        dummy_profile = self._build_dummy_profile(vessel_path, namespace)
        self._vessels.touch_face(
            vessel_path,
            self.resolve_face_id(selector),
            occupancy=sum(record.size for record in files),
            file_count=len(files),
            dummy_profile=dummy_profile,
        )

    def wait_for_camera_frame(self, timeout: float = 10.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._access_cue.latest_frame_copy() is not None:
                return True
            time.sleep(0.1)
        return False

    def wait_for_reference_match(
        self, timeout: float = 10.0, expected_mode: str | None = None
    ) -> bool:
        deadline = time.time() + timeout
        auth_tokens = self._access_cue.auth_tokens()
        while time.time() < deadline:
            matched_mode = self._access_cue.current_match_mode()
            if expected_mode is not None and matched_mode == expected_mode:
                return True
            if expected_mode is None and matched_mode in auth_tokens:
                return True
            time.sleep(0.1)
        return False

    def capture_reference_for_mode(self, mode: str, timeout: float = 10.0) -> None:
        if not self.wait_for_camera_frame(timeout=timeout):
            raise RuntimeError("camera feed did not become available")
        success, message = self._access_cue.capture_reference(mode)
        if not success:
            raise RuntimeError(message)
        if not self.wait_for_reference_match(timeout=timeout, expected_mode=mode):
            raise RuntimeError("object cue captured, but no stable match was detected")

    def collect_auth_sequence(self, timeout: float = 10.0) -> list[str]:
        if not self.wait_for_reference_match(timeout=timeout):
            return [self._access_cue.match_none()]
        return cast(list[str], self._access_cue.auth_sequence(length=1))

    def plaintext_capacity(self, path: str | Path, selector: str = "a") -> int:
        vessel_path = Path(path).expanduser().resolve()
        size_bytes = vessel_path.stat().st_size
        mode = self.resolve_mode(selector)
        vault = PhasmidVault(str(vessel_path), size_mb=size_bytes / (1024 * 1024))
        return vault.container_layout.get_plaintext_capacity(mode, vault.OPEN_ROLE)

    def add_file(
        self,
        vessel_path: str | Path,
        input_path: str | Path,
        open_passphrase: str,
        restricted_passphrase: str | None = None,
        selector: str = "face_a",
        cue_sequence: list[str] | None = None,
        capture_reference: bool = False,
        object_image_path: str | None = None,
        camera_object: bool = False,
        no_object_binding: bool = False,
        emergency_password: str | None = None,
    ) -> StorePayloadResult:
        payload_path = Path(input_path).expanduser().resolve()
        # Validate before reading. Delegating with payload_path.read_bytes()
        # as an argument would pull the plaintext into memory before the
        # selector, the Vessel and the object binding had been checked, so a
        # call that was always going to fail would still have loaded it.
        if not payload_path.is_file():
            raise FileNotFoundError(f"input file not found: {payload_path}")
        self.resolve_mode(selector)
        if not Path(vessel_path).expanduser().resolve().exists():
            raise FileNotFoundError(
                f"vessel file not found: {Path(vessel_path).expanduser().resolve()}"
            )
        result = self.add_payload(
            vessel_path,
            payload_path.name,
            payload_path.read_bytes(),
            open_passphrase,
            restricted_passphrase=restricted_passphrase,
            selector=selector,
            cue_sequence=cue_sequence,
            capture_reference=capture_reference,
            object_image_path=object_image_path,
            camera_object=camera_object,
            no_object_binding=no_object_binding,
            emergency_password=emergency_password,
        )
        return StorePayloadResult(
            vessel_path=result.vessel_path,
            input_path=payload_path,
            bytes_stored=result.bytes_stored,
            mode=result.mode,
        )

    def add_payload(
        self,
        vessel_path: str | Path,
        filename: str,
        payload: bytes,
        open_passphrase: str,
        restricted_passphrase: str | None = None,
        selector: str = "face_a",
        cue_sequence: list[str] | None = None,
        capture_reference: bool = False,
        object_image_path: str | None = None,
        camera_object: bool = False,
        no_object_binding: bool = False,
        emergency_password: str | None = None,
    ) -> StorePayloadResult:
        """Store bytes already in memory into a Vessel face.

        Same path as :meth:`add_file` - object binding, face namespace and
        all - for callers that never had the payload on disk. The WebUI
        receives uploads as bytes, and writing them to a temporary file just
        to hand back a path would put plaintext on disk for no reason.
        """
        vessel = Path(vessel_path).expanduser().resolve()
        name = Path(filename).name or "payload.bin"
        mode = self.resolve_mode(selector)
        if not vessel.exists():
            raise FileNotFoundError(f"vessel file not found: {vessel}")

        stored_binding = self._get_face_binding_record(
            vessel, self.resolve_face_id(selector)
        )
        if (
            object_image_path
            or camera_object
            or no_object_binding
            or self._binding_registered(stored_binding)
        ):
            cue_sequence = self._ensure_object_binding(
                vessel,
                selector,
                object_image_path=object_image_path,
                camera_object=camera_object
                or (
                    not object_image_path
                    and not no_object_binding
                    and self._binding_registered(stored_binding)
                ),
                no_object_binding=no_object_binding,
                register_if_missing=True,
            )
        elif capture_reference:
            self.capture_reference_for_mode(mode)
            cue_sequence = self._access_cue.sequence_for_mode(mode)
        elif cue_sequence is None:
            cue_sequence = self._access_cue.sequence_for_mode(mode)
        cue_sequence = cast(list[str], cue_sequence)

        namespace, _filename = self._read_face_namespace(
            vessel, open_passphrase, selector, cue_sequence
        )
        files = namespace.setdefault("files", {})
        if not isinstance(files, dict):
            raise ValueError("face namespace is invalid")

        files[name] = {
            "data_b64": base64.b64encode(payload).decode("ascii"),
            "size": len(payload),
            "added_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "origin": "manual",
        }
        if emergency_password is None:
            emergency_password = restricted_passphrase
        if emergency_password:
            self._set_face_emergency_password(
                vessel,
                self.resolve_face_id(selector),
                emergency_password,
            )
        self._write_face_namespace(
            vessel,
            open_passphrase,
            emergency_password,
            selector,
            cue_sequence,
            namespace,
        )
        self._vessels.touch_face(
            vessel,
            self.resolve_face_id(selector),
            credentials_initialized=True,
        )
        return StorePayloadResult(
            vessel_path=vessel,
            input_path=Path(name),
            bytes_stored=len(payload),
            mode=mode,
        )

    def list_files(
        self,
        vessel_path: str | Path,
        open_passphrase: str,
        selector: str = "face_a",
        cue_sequence: list[str] | None = None,
        use_attempt_limiter: bool = False,
        object_image_path: str | None = None,
        camera_object: bool = False,
        no_object_binding: bool = False,
    ) -> FaceFileListResult:
        vessel = Path(vessel_path).expanduser().resolve()
        if not self._credentials_initialized(vessel, self.resolve_face_id(selector)):
            raise ValueError("credentials not initialized")
        if use_attempt_limiter:
            limiter = FileAttemptLimiter()
            decision = limiter.check("cli-retrieve")
            if not decision.allowed:
                raise PermissionError("Access temporarily unavailable")
        stored_binding = self._get_face_binding_record(
            vessel, self.resolve_face_id(selector)
        )
        if (
            object_image_path
            or camera_object
            or no_object_binding
            or self._binding_registered(stored_binding)
        ):
            cue_sequence = self._ensure_object_binding(
                vessel,
                selector,
                object_image_path=object_image_path,
                camera_object=camera_object
                or (
                    not object_image_path
                    and not no_object_binding
                    and self._binding_registered(stored_binding)
                ),
                no_object_binding=no_object_binding,
            )
        elif cue_sequence is None:
            cue_sequence = self.collect_auth_sequence()
        cue_sequence = cast(list[str], cue_sequence)
        namespace, _filename = self._read_face_namespace(
            vessel, open_passphrase, selector, cue_sequence
        )
        files = self._namespace_file_records(namespace)
        self._vessels.touch_face(
            vessel,
            self.resolve_face_id(selector),
            occupancy=sum(record.size for record in files),
            file_count=len(files),
        )
        vessel_meta = self._get_meta(vessel)
        return FaceFileListResult(
            vessel=vessel_meta,
            face=self._get_face(vessel_meta, self.resolve_face_id(selector)),
            files=files,
        )

    def remove_file(
        self,
        vessel_path: str | Path,
        stored_name: str,
        open_passphrase: str,
        restricted_passphrase: str | None = None,
        selector: str = "face_a",
        cue_sequence: list[str] | None = None,
        object_image_path: str | None = None,
        camera_object: bool = False,
        no_object_binding: bool = False,
    ) -> FaceResult:
        vessel = Path(vessel_path).expanduser().resolve()
        if not self._credentials_initialized(vessel, self.resolve_face_id(selector)):
            raise ValueError("credentials not initialized")
        stored_binding = self._get_face_binding_record(
            vessel, self.resolve_face_id(selector)
        )
        if (
            object_image_path
            or camera_object
            or no_object_binding
            or self._binding_registered(stored_binding)
        ):
            cue_sequence = self._ensure_object_binding(
                vessel,
                selector,
                object_image_path=object_image_path,
                camera_object=camera_object
                or (
                    not object_image_path
                    and not no_object_binding
                    and self._binding_registered(stored_binding)
                ),
                no_object_binding=no_object_binding,
            )
        elif cue_sequence is None:
            cue_sequence = self.collect_auth_sequence()
        cue_sequence = cast(list[str], cue_sequence)
        namespace, _filename = self._read_face_namespace(
            vessel, open_passphrase, selector, cue_sequence
        )
        files = namespace.get("files", {})
        if not isinstance(files, dict) or stored_name not in files:
            raise FileNotFoundError(f"file not found in selected face: {stored_name}")
        del files[stored_name]
        self._write_face_namespace(
            vessel,
            open_passphrase,
            None,
            selector,
            cue_sequence,
            namespace,
        )
        vessel_meta = self._get_meta(vessel)
        return FaceResult(
            vessel=vessel_meta,
            face=self._get_face(vessel_meta, self.resolve_face_id(selector)),
        )

    def inspect_dummy_profile(
        self,
        vessel_path: str | Path,
        face_id: str = "face_a",
    ) -> DummyProfileResult:
        vessel = self._get_meta(Path(vessel_path).expanduser().resolve())
        face = self._get_face(vessel, self.resolve_face_id(face_id))
        return DummyProfileResult(
            vessel=vessel,
            face=face,
            profile=face.dummy_profile,
            recommended_action=self._recommended_action(face.dummy_profile),
        )

    def generate_dummy_profile(
        self,
        vessel_path: str | Path,
        open_passphrase: str,
        restricted_passphrase: str,
        selector: str = "face_a",
        target_occupancy: str | None = None,
        size_spec: str | None = None,
        cue_sequence: list[str] | None = None,
        capture_reference: bool = False,
    ) -> DummyProfileResult:
        vessel = Path(vessel_path).expanduser().resolve()
        mode = self.resolve_mode(selector)
        if capture_reference:
            self.capture_reference_for_mode(mode)
            cue_sequence = self._access_cue.sequence_for_mode(mode)
        elif cue_sequence is None:
            cue_sequence = self._access_cue.sequence_for_mode(mode)
        cue_sequence = cast(list[str], cue_sequence)

        namespace, _filename = self._read_face_namespace(
            vessel, open_passphrase, selector, cue_sequence
        )
        files = namespace.setdefault("files", {})
        if not isinstance(files, dict):
            raise ValueError("face namespace is invalid")

        for name in list(files):
            item = files.get(name)
            if (
                isinstance(item, dict)
                and str(item.get("origin", "")) == _GENERATED_PLAUSIBILITY_ORIGIN
            ):
                del files[name]

        vessel_size = vessel.stat().st_size
        if size_spec:
            target_bytes = self.parse_storage_size_spec(size_spec)
        else:
            occupancy_ratio = self.parse_occupancy_spec(target_occupancy or "15%")
            target_bytes = int(vessel_size * occupancy_ratio)

        if target_bytes <= 0:
            raise ValueError("target plausibility size must be greater than zero")

        specs = self._build_generated_file_specs(target_bytes)
        max_payload = self.plaintext_capacity(vessel, selector)
        for filename, payload in specs:
            files[filename] = self._generated_entry(filename, payload)
            encoded, _namespace_name = self._encode_namespace(namespace)
            if len(encoded) > max_payload:
                del files[filename]
                break

        if not any(
            isinstance(item, dict)
            and str(item.get("origin", "")) == _GENERATED_PLAUSIBILITY_ORIGIN
            for item in files.values()
        ):
            raise ValueError(
                "target size does not fit within the selected face capacity"
            )

        self._write_face_namespace(
            vessel,
            open_passphrase,
            restricted_passphrase,
            selector,
            cue_sequence,
            namespace,
        )
        return self.inspect_dummy_profile(vessel, selector)

    def clear_dummy_profile(
        self,
        vessel_path: str | Path,
        open_passphrase: str,
        restricted_passphrase: str,
        selector: str = "face_a",
        cue_sequence: list[str] | None = None,
    ) -> DummyProfileResult:
        vessel = Path(vessel_path).expanduser().resolve()
        if cue_sequence is None:
            cue_sequence = self._access_cue.sequence_for_mode(
                self.resolve_mode(selector)
            )
        cue_sequence = cast(list[str], cue_sequence)
        namespace, _filename = self._read_face_namespace(
            vessel, open_passphrase, selector, cue_sequence
        )
        files = namespace.get("files", {})
        if not isinstance(files, dict):
            raise ValueError("face namespace is invalid")
        for name in list(files):
            item = files.get(name)
            if (
                isinstance(item, dict)
                and str(item.get("origin", "")) == _GENERATED_PLAUSIBILITY_ORIGIN
            ):
                del files[name]
        self._write_face_namespace(
            vessel,
            open_passphrase,
            restricted_passphrase,
            selector,
            cue_sequence,
            namespace,
        )
        return self.inspect_dummy_profile(vessel, selector)

    def destroy_face(
        self,
        vessel_path: str | Path,
        emergency_password: str,
        selector: str = "face_a",
        object_image_path: str | None = None,
        camera_object: bool = False,
        confirmation: str = "",
    ) -> EmergencyDestroyResult:
        if confirmation.strip() != "DESTROY FACE":
            raise ValueError("confirmation rejected")
        vessel = Path(vessel_path).expanduser().resolve()
        face_id = self.resolve_face_id(selector)
        if not self._credentials_initialized(vessel, face_id):
            raise ValueError("credentials not initialized")
        self._ensure_object_binding(
            vessel,
            selector,
            object_image_path=object_image_path,
            camera_object=camera_object,
        )
        if not self._verify_face_emergency_password(
            vessel, face_id, emergency_password
        ):
            raise ValueError("emergency password mismatch")
        mode = self.resolve_mode(selector)
        vault = PhasmidVault(str(vessel), size_mb=vessel.stat().st_size / (1024 * 1024))
        vault.purge_mode(mode)
        self._vessels.touch_face(
            vessel,
            face_id,
            occupancy=0,
            file_count=0,
            status="available",
            credentials_initialized=False,
            object_binding_initialized=False,
            object_binding={},
            emergency_auth={},
            dummy_profile={
                "dummy_file_count": 0,
                "dummy_total_size": 0,
                "occupancy_ratio": 0.0,
                "file_type_distribution": {},
                "plausibility_score": 0,
                "plausibility_level": "LOW",
                "last_updated_at": self._current_timestamp(),
            },
        )
        return EmergencyDestroyResult(
            vessel_path=vessel,
            face_id=face_id,
            scope="face",
        )

    def destroy_vessel(
        self,
        vessel_path: str | Path,
        emergency_password: str,
        selector: str = "face_a",
        object_image_path: str | None = None,
        camera_object: bool = False,
        confirmation: str = "",
    ) -> EmergencyDestroyResult:
        if confirmation.strip() != "DESTROY VESSEL":
            raise ValueError("confirmation rejected")
        vessel = Path(vessel_path).expanduser().resolve()
        face_id = self.resolve_face_id(selector)
        if not self._credentials_initialized(vessel, face_id):
            raise ValueError("credentials not initialized")
        self._ensure_object_binding(
            vessel,
            selector,
            object_image_path=object_image_path,
            camera_object=camera_object,
        )
        if not self._verify_face_emergency_password(
            vessel, face_id, emergency_password
        ):
            raise ValueError("emergency password mismatch")
        vault = PhasmidVault(str(vessel), size_mb=vessel.stat().st_size / (1024 * 1024))
        vault.silent_brick()
        self._vessels.unregister(vessel)
        return EmergencyDestroyResult(
            vessel_path=vessel,
            face_id=face_id,
            scope="vessel",
        )

    def store_file(
        self,
        vessel_path: str | Path,
        input_path: str | Path,
        open_passphrase: str,
        restricted_passphrase: str | None = None,
        selector: str = "a",
        cue_sequence: list[str] | None = None,
        capture_reference: bool = False,
        object_image_path: str | None = None,
        camera_object: bool = False,
        no_object_binding: bool = False,
        emergency_password: str | None = None,
    ) -> StorePayloadResult:
        return self.add_file(
            vessel_path,
            input_path,
            open_passphrase,
            restricted_passphrase,
            selector=selector,
            cue_sequence=cue_sequence,
            capture_reference=capture_reference,
            object_image_path=object_image_path,
            camera_object=camera_object,
            no_object_binding=no_object_binding,
            emergency_password=emergency_password,
        )

    def retrieve_payload(
        self,
        vessel_path: str | Path,
        open_passphrase: str,
        selector: str | None = None,
        cue_sequence: list[str] | None = None,
        use_attempt_limiter: bool = False,
        object_image_path: str | None = None,
        camera_object: bool = False,
        no_object_binding: bool = False,
        filename: str | None = None,
    ) -> tuple[bytes, RetrievePayloadResult]:
        """Recover a stored payload as bytes, without writing it to disk.

        Same path as :meth:`retrieve_file` including the object-cue check.
        The bytes are returned alongside the result rather than carried on
        it, so a plaintext payload never ends up in the dataclass repr that
        the CLI and the operator log print.
        """
        collected: dict[str, bytes] = {}
        result = self.retrieve_file(
            vessel_path,
            open_passphrase,
            output_path=None,
            selector=selector,
            cue_sequence=cue_sequence,
            use_attempt_limiter=use_attempt_limiter,
            object_image_path=object_image_path,
            camera_object=camera_object,
            no_object_binding=no_object_binding,
            filename=filename,
            _payload_sink=collected,
        )
        return collected.get("data", b""), result

    def retrieve_file(
        self,
        vessel_path: str | Path,
        open_passphrase: str,
        output_path: str | Path | None = None,
        selector: str | None = None,
        cue_sequence: list[str] | None = None,
        use_attempt_limiter: bool = False,
        object_image_path: str | None = None,
        camera_object: bool = False,
        no_object_binding: bool = False,
        filename: str | None = None,
        _payload_sink: dict[str, bytes] | None = None,
    ) -> RetrievePayloadResult:
        vessel = Path(vessel_path).expanduser().resolve()
        if not vessel.exists():
            raise FileNotFoundError(f"vessel file not found: {vessel}")
        if selector is not None and not self._credentials_initialized(
            vessel, self.resolve_face_id(selector)
        ):
            raise ValueError("credentials not initialized")

        if use_attempt_limiter:
            limiter = FileAttemptLimiter()
            decision = limiter.check("cli-retrieve")
            if not decision.allowed:
                raise PermissionError("Access temporarily unavailable")

        candidate_selectors = [selector] if selector else ["face_a", "face_b"]
        namespace = None
        accessed_selector = None
        for candidate in candidate_selectors:
            if not self._credentials_initialized(
                vessel, self.resolve_face_id(str(candidate))
            ):
                continue
            try:
                active_cue_sequence = cue_sequence
                stored_binding = self._get_face_binding_record(
                    vessel, self.resolve_face_id(str(candidate))
                )
                if (
                    object_image_path
                    or camera_object
                    or no_object_binding
                    or self._binding_registered(stored_binding)
                ):
                    active_cue_sequence = self._ensure_object_binding(
                        vessel,
                        str(candidate),
                        object_image_path=object_image_path,
                        camera_object=camera_object
                        or (
                            not object_image_path
                            and not no_object_binding
                            and self._binding_registered(stored_binding)
                        ),
                        no_object_binding=no_object_binding,
                    )
                elif active_cue_sequence is None:
                    active_cue_sequence = self.collect_auth_sequence()
                if (
                    not active_cue_sequence
                    or active_cue_sequence[0] == self._access_cue.match_none()
                ):
                    raise ValueError("no bound object matched")
                namespace, _filename = self._read_face_namespace(
                    vessel,
                    open_passphrase,
                    str(candidate),
                    cast(list[str], active_cue_sequence),
                )
                accessed_selector = str(candidate)
                break
            except ValueError:
                if (
                    selector is not None
                    or object_image_path
                    or camera_object
                    or no_object_binding
                ):
                    raise
                continue

        if namespace is None or accessed_selector is None:
            raise ValueError("password mismatch")
        files = self._namespace_file_records(namespace)
        if not files:
            raise FileNotFoundError("no file is stored in the selected face")
        # A face holds many files, so "which one" has to be decided. Named
        # selection first, then the output filename, and otherwise the most
        # recently stored. Falling back to the alphabetically first record
        # made every later store unreachable for callers that name neither -
        # the WebUI names neither, so a second upload to the same entry
        # silently became unretrievable through the interface that wrote it.
        chosen = max(files, key=lambda record: (record.added_at, record.name))
        desired_name = filename or (Path(output_path).name if output_path else "")
        if desired_name:
            chosen = next(
                (record for record in files if record.name == desired_name),
                chosen,
            )
        raw_files = namespace.get("files", {})
        if not isinstance(raw_files, dict) or chosen.name not in raw_files:
            raise FileNotFoundError("stored file could not be resolved")
        item = raw_files[chosen.name]
        if not isinstance(item, dict):
            raise ValueError("stored file metadata is invalid")
        data = base64.b64decode(str(item.get("data_b64", "")).encode("ascii"))
        if _payload_sink is not None:
            _payload_sink["data"] = data
        filename = chosen.name
        password_role = PhasmidVault.OPEN_ROLE
        accessed_mode = self.resolve_mode(accessed_selector)
        self._vessels.touch_face(
            vessel,
            self.resolve_face_id(accessed_selector),
            occupancy=sum(record.size for record in files),
            file_count=len(files),
        )

        target_path: Path | None = None
        if output_path is not None:
            target_path = Path(output_path).expanduser().resolve()
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_bytes(data)

        return RetrievePayloadResult(
            vessel_path=vessel,
            output_path=target_path,
            bytes_retrieved=len(data),
            filename=filename,
            mode=accessed_mode,
            password_role=password_role,
        )
