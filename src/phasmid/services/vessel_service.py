from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ..models.vessel import DummyProfileMeta, FaceMeta, VesselMeta, VesselPosture
from .object_binding_service import ObjectBindingService
from .profile_service import _ensure_dir, config_dir

_REGISTRY_PATH_KEY = "vessel_registry"
DEFAULT_FACE_SPECS = (
    ("face_a", "Disclosure Face 1", "a"),
    ("face_b", "Disclosure Face 2", "b"),
)

REVEALING_TERMS = frozenset(
    {
        "secret",
        "hidden",
        "janus",
        "real",
        "fake",
        "decoy",
        "true",
        "covert",
    }
)
_OBJECT_BINDING = ObjectBindingService()


def _string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


def _int_value(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, (str, bytes, bytearray)):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def _default_face_record(face_id: str, label: str, selector: str) -> dict[str, object]:
    return {
        "face_id": face_id,
        "label": label,
        "created_at": _utc_now(),
        "last_accessed": "",
        "occupancy": 0,
        "file_count": 0,
        "status": "available",
        "selector": selector,
        "credentials_initialized": False,
        "object_binding_initialized": False,
        "dummy_profile": _default_dummy_profile_record(),
        "object_binding": {},
        "emergency_auth": {},
    }


def _default_faces() -> list[dict[str, object]]:
    return [
        _default_face_record(face_id, label, selector)
        for face_id, label, selector in DEFAULT_FACE_SPECS
    ]


def _default_dummy_profile_record() -> dict[str, object]:
    return {
        "dummy_file_count": 0,
        "dummy_total_size": 0,
        "occupancy_ratio": 0.0,
        "file_type_distribution": {},
        "plausibility_score": 0,
        "plausibility_level": "LOW",
        "last_updated_at": "",
    }


def _float_value(value: object, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, (str, bytes, bytearray)):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def _string_int_dict(value: object) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    return {str(key): _int_value(item) for key, item in value.items()}


def _normalize_dummy_profile_record(item: object) -> dict[str, object]:
    if not isinstance(item, dict):
        item = {}
    return {
        "dummy_file_count": _int_value(item.get("dummy_file_count", 0)),
        "dummy_total_size": _int_value(item.get("dummy_total_size", 0)),
        "occupancy_ratio": _float_value(item.get("occupancy_ratio", 0.0)),
        "file_type_distribution": _string_int_dict(
            item.get("file_type_distribution", {})
        ),
        "plausibility_score": _int_value(item.get("plausibility_score", 0)),
        "plausibility_level": str(item.get("plausibility_level", "LOW")).upper(),
        "last_updated_at": str(item.get("last_updated_at", "")),
    }


def _aggregate_dummy_profile(
    faces: list[dict[str, object]],
) -> dict[str, object]:
    aggregate = _default_dummy_profile_record()
    distribution: dict[str, int] = {}
    last_updated = ""
    highest_level = "LOW"
    highest_score = 0
    total_ratio = 0.0

    level_rank = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
    for face in faces:
        profile = _normalize_dummy_profile_record(face.get("dummy_profile", {}))
        aggregate["dummy_file_count"] = _int_value(aggregate["dummy_file_count"]) + _int_value(profile["dummy_file_count"])
        aggregate["dummy_total_size"] = _int_value(aggregate["dummy_total_size"]) + _int_value(profile["dummy_total_size"])
        total_ratio += _float_value(profile["occupancy_ratio"])
        highest_score = max(highest_score, _int_value(profile["plausibility_score"]))
        level = str(profile["plausibility_level"]).upper()
        if level_rank.get(level, 0) > level_rank.get(highest_level, 0):
            highest_level = level
        updated_at = str(profile["last_updated_at"])
        if updated_at > last_updated:
            last_updated = updated_at
        for ext, count in _string_int_dict(profile["file_type_distribution"]).items():
            distribution[ext] = distribution.get(ext, 0) + count

    aggregate["occupancy_ratio"] = total_ratio
    aggregate["file_type_distribution"] = distribution
    aggregate["plausibility_score"] = highest_score
    aggregate["plausibility_level"] = highest_level
    aggregate["last_updated_at"] = last_updated
    return aggregate


def _normalize_face_record(
    item: dict[str, object],
    default_label: str = "",
    default_selector: str = "",
) -> dict[str, object]:
    return {
        "face_id": str(item.get("face_id", "")),
        "label": str(item.get("label", default_label)),
        "created_at": str(item.get("created_at", "")),
        "last_accessed": str(item.get("last_accessed", "")),
        "occupancy": _int_value(item.get("occupancy", 0)),
        "file_count": _int_value(item.get("file_count", 0)),
        "status": str(item.get("status", "available")),
        "selector": str(item.get("selector", default_selector)),
        "credentials_initialized": bool(item.get("credentials_initialized", False)),
        "object_binding_initialized": bool(
            item.get("object_binding_initialized", False)
        ),
        "dummy_profile": _normalize_dummy_profile_record(item.get("dummy_profile", {})),
        "object_binding": _OBJECT_BINDING.normalize_record(
            item.get("object_binding", {})
        ),
        "emergency_auth": _normalize_emergency_auth_record(
            item.get("emergency_auth", {})
        ),
    }


def _normalize_emergency_auth_record(item: object) -> dict[str, object]:
    if not isinstance(item, dict):
        item = {}
    return {
        "salt_b64": str(item.get("salt_b64", "")),
        "hash_b64": str(item.get("hash_b64", "")),
        "updated_at": str(item.get("updated_at", "")),
    }


def _normalize_faces(value: object) -> list[dict[str, object]]:
    default_by_id = {
        face_id: _default_face_record(face_id, label, selector)
        for face_id, label, selector in DEFAULT_FACE_SPECS
    }
    normalized: list[dict[str, object]] = []
    if isinstance(value, list):
        for item in value:
            if not isinstance(item, dict):
                continue
            face_id = str(item.get("face_id", ""))
            if not face_id:
                continue
            default = default_by_id.get(face_id, {})
            normalized.append(
                _normalize_face_record(
                    item,
                    default_label=str(default.get("label", "")),
                    default_selector=str(default.get("selector", "")),
                )
            )

    seen = {str(face["face_id"]) for face in normalized}
    for face_id, label, selector in DEFAULT_FACE_SPECS:
        if face_id not in seen:
            normalized.append(_default_face_record(face_id, label, selector))
    return normalized


def _faces_to_labels(faces: list[dict[str, object]]) -> list[str]:
    return [str(face.get("label", "")) for face in faces]


def _registry_path() -> Path:
    return config_dir() / "vessel_registry.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _normalize_registry_record(item: str | dict[str, object]) -> dict[str, object]:
    if isinstance(item, str):
        return {
            "path": item,
            "label": "",
            "face_labels": [label for _face_id, label, _selector in DEFAULT_FACE_SPECS],
            "faces": _default_faces(),
            "is_open": False,
            "open_count": 0,
            "last_opened_at": "",
            "last_closed_at": "",
            "active_face_id": "",
        }
    faces = _normalize_faces(item.get("faces", []))
    return {
        "path": str(item.get("path", "")),
        "label": str(item.get("label", "")),
        "face_labels": _faces_to_labels(faces),
        "faces": faces,
        "dummy_profile": _aggregate_dummy_profile(faces),
        "is_open": bool(item.get("is_open", False)),
        "open_count": _int_value(item.get("open_count", 0)),
        "last_opened_at": str(item.get("last_opened_at", "")),
        "last_closed_at": str(item.get("last_closed_at", "")),
        "active_face_id": str(item.get("active_face_id", "")),
    }


def _load_registry() -> list[dict[str, object]]:
    rp = _registry_path()
    if not rp.exists():
        return []
    try:
        with open(rp, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [_normalize_registry_record(item) for item in data.get("vessels", [])]
    except Exception:
        return []


def _save_registry(records: list[dict[str, object]]) -> None:
    rp = _registry_path()
    _ensure_dir(rp.parent)
    with open(rp, "w", encoding="utf-8") as f:
        json.dump({"vessels": records}, f, indent=2)
    try:
        rp.chmod(0o600)
    except OSError:
        pass


def register_vessel(path: str | Path) -> None:
    path = str(Path(path).resolve())
    existing = _load_registry()
    if not any(record["path"] == path for record in existing):
        existing.append(_normalize_registry_record(path))
        _save_registry(existing)


def unregister_vessel(path: str | Path) -> bool:
    path = str(Path(path).resolve())
    existing = _load_registry()
    filtered = [record for record in existing if record["path"] != path]
    if len(filtered) != len(existing):
        existing = filtered
        _save_registry(existing)
        return True
    return False


def _update_registry_record(
    path: str | Path,
    *,
    is_open: bool | None = None,
    increment_open_count: bool = False,
    label: str | None = None,
    face_labels: list[str] | None = None,
    faces: list[dict[str, object]] | None = None,
    active_face_id: str | None = None,
) -> dict[str, object]:
    resolved = str(Path(path).resolve())
    existing = _load_registry()
    record = None
    for item in existing:
        if item["path"] == resolved:
            record = item
            break
    if record is None:
        record = _normalize_registry_record(resolved)
        existing.append(record)

    if is_open is not None:
        record["is_open"] = is_open
        if is_open:
            record["last_opened_at"] = _utc_now()
            if increment_open_count:
                record["open_count"] = _int_value(record.get("open_count", 0)) + 1
        else:
            record["last_closed_at"] = _utc_now()
    if label is not None:
        record["label"] = label
    if face_labels is not None:
        record["face_labels"] = face_labels
    if faces is not None:
        normalized_faces = _normalize_faces(faces)
        record["faces"] = normalized_faces
        record["face_labels"] = _faces_to_labels(normalized_faces)
        record["dummy_profile"] = _aggregate_dummy_profile(normalized_faces)
    if active_face_id is not None:
        record["active_face_id"] = active_face_id
    _save_registry(existing)
    return record


def _find_face(record: dict[str, object], face_id: str) -> dict[str, object] | None:
    for face in _normalize_faces(record.get("faces", [])):
        if str(face.get("face_id", "")) == face_id:
            return face
    return None


def create_face(
    path: str | Path,
    face_id: str,
    label: str,
    selector: str,
) -> dict[str, object]:
    record = _update_registry_record(path)
    faces = _normalize_faces(record.get("faces", []))
    for face in faces:
        if str(face.get("face_id", "")) == face_id:
            face["label"] = label or str(face.get("label", ""))
            face["selector"] = selector or str(face.get("selector", ""))
            face["status"] = str(face.get("status", "available"))
            return _update_registry_record(path, faces=faces)
    faces.append(_default_face_record(face_id, label, selector))
    return _update_registry_record(path, faces=faces)


def update_face_access(
    path: str | Path,
    face_id: str,
    *,
    opened: bool = False,
    closed: bool = False,
    status: str | None = None,
    occupancy: int | None = None,
    file_count: int | None = None,
    dummy_profile: dict[str, object] | None = None,
    object_binding: dict[str, object] | None = None,
    emergency_auth: dict[str, object] | None = None,
    credentials_initialized: bool | None = None,
    object_binding_initialized: bool | None = None,
) -> dict[str, object]:
    record = _update_registry_record(path)
    faces = _normalize_faces(record.get("faces", []))
    face = next((item for item in faces if str(item.get("face_id", "")) == face_id), None)
    if face is None:
        raise ValueError(f"unsupported face id: {face_id}")

    if occupancy is not None:
        face["occupancy"] = occupancy
    if file_count is not None:
        face["file_count"] = file_count
    if status is not None:
        face["status"] = status
    if dummy_profile is not None:
        face["dummy_profile"] = _normalize_dummy_profile_record(dummy_profile)
    if object_binding is not None:
        face["object_binding"] = _OBJECT_BINDING.normalize_record(object_binding)
    if emergency_auth is not None:
        face["emergency_auth"] = _normalize_emergency_auth_record(emergency_auth)
    if credentials_initialized is not None:
        face["credentials_initialized"] = credentials_initialized
    if object_binding_initialized is not None:
        face["object_binding_initialized"] = object_binding_initialized
    if opened:
        face["last_accessed"] = _utc_now()
        face["status"] = "open"
        record = _update_registry_record(
            path,
            is_open=True,
            increment_open_count=True,
            faces=faces,
            active_face_id=face_id,
        )
        return record
    if closed:
        face["status"] = (
            "occupied"
            if _int_value(face.get("file_count", 0)) > 0
            else "available"
        )
        record = _update_registry_record(
            path,
            is_open=False,
            faces=faces,
            active_face_id="",
        )
        return record
    face["last_accessed"] = _utc_now()
    face["status"] = (
        "occupied" if _int_value(face.get("file_count", 0)) > 0 else "available"
    )
    return _update_registry_record(path, faces=faces)


def open_vessel(path: str | Path, face_id: str = "face_a") -> dict[str, object]:
    return update_face_access(path, face_id, opened=True)


def close_vessel(path: str | Path) -> dict[str, object]:
    record = _update_registry_record(path)
    active_face_id = str(record.get("active_face_id", "")) or "face_a"
    return update_face_access(path, active_face_id, closed=True)


def get_vessel_record(path: str | Path) -> dict[str, object] | None:
    resolved = str(Path(path).resolve())
    for record in _load_registry():
        if record["path"] == resolved:
            return record
    return None


def list_vessels(extra_dir: str | None = None) -> list[VesselMeta]:
    paths: list[Path] = []
    records_by_path: dict[Path, dict[str, object]] = {}

    for record in _load_registry():
        pp = Path(str(record["path"]))
        if pp.exists():
            paths.append(pp)
            records_by_path[pp.resolve()] = record

    if extra_dir:
        ed = Path(extra_dir).expanduser()
        if ed.is_dir():
            for f in ed.glob("*.vessel"):
                if f not in paths:
                    paths.append(f)

    return [_meta_for(p, records_by_path.get(p.resolve())) for p in paths]


def _meta_for(path: Path, record: dict[str, object] | None = None) -> VesselMeta:
    try:
        size = path.stat().st_size
    except OSError:
        size = 0
    normalized_faces = _normalize_faces((record or {}).get("faces", []))

    return VesselMeta(
        path=path,
        name=path.name,
        size_bytes=size,
        header_status="absent",
        magic_bytes_status="absent",
        face_count=len(normalized_faces),
        posture=VesselPosture.OPERATIONAL if size > 0 else VesselPosture.UNKNOWN,
        label=str((record or {}).get("label", "")),
        face_labels=_string_list((record or {}).get("face_labels", [])),
        faces=[
            FaceMeta(
                face_id=str(face.get("face_id", "")),
                label=str(face.get("label", "")),
                created_at=str(face.get("created_at", "")),
                last_accessed=str(face.get("last_accessed", "")),
                occupancy=_int_value(face.get("occupancy", 0)),
                file_count=_int_value(face.get("file_count", 0)),
                status=str(face.get("status", "available")),
                selector=str(face.get("selector", "")),
                credentials_initialized=bool(
                    face.get("credentials_initialized", False)
                ),
                object_binding_initialized=bool(
                    face.get("object_binding_initialized", False)
                ),
                dummy_profile=DummyProfileMeta(
                    dummy_file_count=_int_value(
                        _normalize_dummy_profile_record(
                            face.get("dummy_profile", {})
                        ).get("dummy_file_count", 0)
                    ),
                    dummy_total_size=_int_value(
                        _normalize_dummy_profile_record(
                            face.get("dummy_profile", {})
                        ).get("dummy_total_size", 0)
                    ),
                    occupancy_ratio=_float_value(
                        _normalize_dummy_profile_record(
                            face.get("dummy_profile", {})
                        ).get("occupancy_ratio", 0.0)
                    ),
                    file_type_distribution=_string_int_dict(
                        _normalize_dummy_profile_record(
                            face.get("dummy_profile", {})
                        ).get("file_type_distribution", {})
                    ),
                    plausibility_score=_int_value(
                        _normalize_dummy_profile_record(
                            face.get("dummy_profile", {})
                        ).get("plausibility_score", 0)
                    ),
                    plausibility_level=str(
                        _normalize_dummy_profile_record(
                            face.get("dummy_profile", {})
                        ).get("plausibility_level", "LOW")
                    ),
                    last_updated_at=str(
                        _normalize_dummy_profile_record(
                            face.get("dummy_profile", {})
                        ).get("last_updated_at", "")
                    ),
                ),
            )
            for face in normalized_faces
        ],
        is_open=bool((record or {}).get("is_open", False)),
        open_count=_int_value((record or {}).get("open_count", 0)),
        last_opened_at=str((record or {}).get("last_opened_at", "")),
        last_closed_at=str((record or {}).get("last_closed_at", "")),
        dummy_profile=DummyProfileMeta(
            dummy_file_count=_int_value(
                _normalize_dummy_profile_record(
                    (record or {}).get("dummy_profile", {})
                ).get("dummy_file_count", 0)
            ),
            dummy_total_size=_int_value(
                _normalize_dummy_profile_record(
                    (record or {}).get("dummy_profile", {})
                ).get("dummy_total_size", 0)
            ),
            occupancy_ratio=_float_value(
                _normalize_dummy_profile_record(
                    (record or {}).get("dummy_profile", {})
                ).get("occupancy_ratio", 0.0)
            ),
            file_type_distribution=_string_int_dict(
                _normalize_dummy_profile_record(
                    (record or {}).get("dummy_profile", {})
                ).get("file_type_distribution", {})
            ),
            plausibility_score=_int_value(
                _normalize_dummy_profile_record(
                    (record or {}).get("dummy_profile", {})
                ).get("plausibility_score", 0)
            ),
            plausibility_level=str(
                _normalize_dummy_profile_record(
                    (record or {}).get("dummy_profile", {})
                ).get("plausibility_level", "LOW")
            ),
            last_updated_at=str(
                _normalize_dummy_profile_record(
                    (record or {}).get("dummy_profile", {})
                ).get("last_updated_at", "")
            ),
        ),
    )


def check_filename_warnings(path: str | Path) -> list[str]:
    name = Path(path).name.lower()
    warnings = []
    for term in REVEALING_TERMS:
        if term in name:
            warnings.append(
                f'Filename contains revealing term "{term}". '
                "Consider using a neutral name."
            )
    return warnings


def redact_path(path: str | Path) -> str:
    p = Path(path)
    home = Path.home()
    try:
        rel = p.relative_to(home)
        parts = rel.parts
        if len(parts) > 3:
            return f"~/{parts[0]}/.../{parts[-1]}"
        return f"~/{rel}"
    except ValueError:
        return str(p)


class VesselService:
    def register(self, path: str | Path) -> None:
        register_vessel(path)

    def unregister(self, path: str | Path) -> bool:
        return unregister_vessel(path)

    def list_all(self, extra_dir: str | None = None) -> list[VesselMeta]:
        return list_vessels(extra_dir)

    def open(self, path: str | Path) -> dict[str, object]:
        return open_vessel(path)

    def open_face(self, path: str | Path, face_id: str) -> dict[str, object]:
        return open_vessel(path, face_id=face_id)

    def close(self, path: str | Path) -> dict[str, object]:
        return close_vessel(path)

    def get_record(self, path: str | Path) -> dict[str, object] | None:
        return get_vessel_record(path)

    def set_metadata(
        self,
        path: str | Path,
        *,
        label: str | None = None,
        face_labels: list[str] | None = None,
    ) -> dict[str, object]:
        return _update_registry_record(path, label=label, face_labels=face_labels)

    def create_face(
        self, path: str | Path, face_id: str, label: str, selector: str
    ) -> dict[str, object]:
        return create_face(path, face_id, label, selector)

    def touch_face(
        self,
        path: str | Path,
        face_id: str,
        *,
        opened: bool = False,
        closed: bool = False,
        status: str | None = None,
        occupancy: int | None = None,
        file_count: int | None = None,
        dummy_profile: dict[str, object] | None = None,
        object_binding: dict[str, object] | None = None,
        emergency_auth: dict[str, object] | None = None,
        credentials_initialized: bool | None = None,
        object_binding_initialized: bool | None = None,
    ) -> dict[str, object]:
        return update_face_access(
            path,
            face_id,
            opened=opened,
            closed=closed,
            status=status,
            occupancy=occupancy,
            file_count=file_count,
            dummy_profile=dummy_profile,
            object_binding=object_binding,
            emergency_auth=emergency_auth,
            credentials_initialized=credentials_initialized,
            object_binding_initialized=object_binding_initialized,
        )

    def check_filename_warnings(self, path: str | Path) -> list[str]:
        return check_filename_warnings(path)

    def redact_path(self, path: str | Path) -> str:
        return redact_path(path)
