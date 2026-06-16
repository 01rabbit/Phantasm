from __future__ import annotations

import math
from pathlib import Path

from ..models.inspection import InspectionField, InspectionResult
from .vessel_service import VesselService

_SAMPLE_SIZE = 65536
_COMMON_MAGIC = [
    (b"\x89PNG", "PNG image"),
    (b"PK\x03\x04", "ZIP archive"),
    (b"\x1f\x8b", "gzip compressed"),
    (b"MZ", "Windows PE executable"),
    (b"\x7fELF", "ELF binary"),
    (b"RIFF", "RIFF container"),
    (b"\xff\xd8\xff", "JPEG image"),
    (b"%PDF", "PDF document"),
    (b"SQLite", "SQLite database"),
    (b"OggS", "Ogg stream"),
    (b"fLaC", "FLAC audio"),
    (b"ID3", "MP3 audio"),
]


def _estimate_entropy(data: bytes) -> float:
    if not data:
        return 0.0
    freq = [0] * 256
    for b in data:
        freq[b] += 1
    n = len(data)
    entropy = 0.0
    for count in freq:
        if count > 0:
            p = count / n
            entropy -= p * math.log2(p)
    return entropy


def _entropy_label(entropy: float) -> str:
    if entropy >= 7.8:
        return "high / random-like"
    if entropy >= 6.0:
        return "moderate"
    return "low"


def _detect_magic(data: bytes) -> str:
    for magic, label in _COMMON_MAGIC:
        if data.startswith(magic):
            return label
    return "unknown"


def inspect_vessel(path: str | Path) -> InspectionResult:
    p = Path(path)
    if not p.exists():
        return InspectionResult(
            path=p,
            error=f"File does not exist: {p}",
        )
    if not p.is_file():
        return InspectionResult(
            path=p,
            error=f"Path is not a file: {p}",
        )

    try:
        size = p.stat().st_size
    except OSError as exc:
        return InspectionResult(path=p, error=str(exc))

    try:
        with open(p, "rb") as f:
            sample = f.read(_SAMPLE_SIZE)
    except OSError as exc:
        return InspectionResult(path=p, error=str(exc))

    entropy = _estimate_entropy(sample) if sample else 0.0
    detected_type = _detect_magic(sample) if sample else "unknown"
    magic_status = (
        "no obvious magic bytes detected"
        if detected_type == "unknown"
        else f"detected: {detected_type}"
    )

    fields = [
        InspectionField("File", str(p)),
        InspectionField("Size", _human_size(size)),
        InspectionField("Header", "no recognized header detected"),
        InspectionField("Magic Bytes", magic_status),
        InspectionField("Entropy", _entropy_label(entropy), f"{entropy:.2f} bits/byte"),
        InspectionField("Recognized Type", detected_type),
        InspectionField("Vessel Claim", "not asserted"),
    ]
    vessel_meta = None
    for candidate in VesselService().list_all():
        if candidate.path.resolve() == p.resolve():
            vessel_meta = candidate
            break
    if vessel_meta is not None:
        face_summary = ", ".join(
            f"{face.face_id}:{face.status}:{face.file_count} files:{face.occupancy} bytes:{face.last_accessed or '-'}"
            for face in vessel_meta.faces
        )
        plausibility_summary = ", ".join(
            f"{face.face_id}:{face.dummy_profile.plausibility_level}:"
            f"{face.dummy_profile.plausibility_score}:"
            f"{face.dummy_profile.dummy_file_count} files:"
            f"{face.dummy_profile.occupancy_ratio * 100:.1f}%"
            for face in vessel_meta.faces
        )
        fields.extend(
            [
                InspectionField("Face Count", str(vessel_meta.face_count)),
                InspectionField("Face Registry", face_summary or "not recorded"),
                InspectionField(
                    "Plausibility Summary",
                    plausibility_summary or "not recorded",
                ),
            ]
        )

    notes = []
    if detected_type != "unknown":
        notes.append(
            f"File appears to contain recognizable data ({detected_type}). "
            "This may reduce deniability."
        )
    if entropy < 6.0:
        notes.append(
            "Entropy is below typical random-data threshold. "
            "Content may be identifiable."
        )

    return InspectionResult(path=p, fields=fields, notes=notes)


def _human_size(n: int) -> str:
    b: float = float(n)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if b < 1024:
            return f"{b:.0f} {unit}" if unit == "B" else f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PiB"


class InspectionService:
    def inspect(self, path: str | Path) -> InspectionResult:
        return inspect_vessel(path)
