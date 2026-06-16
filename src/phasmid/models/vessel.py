from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class VesselPosture(str, Enum):
    OPERATIONAL = "operational"
    UNREGISTERED = "unregistered"
    UNKNOWN = "unknown"


@dataclass
class DummyProfileMeta:
    dummy_file_count: int = 0
    dummy_total_size: int = 0
    occupancy_ratio: float = 0.0
    file_type_distribution: dict[str, int] = field(default_factory=dict)
    plausibility_score: int = 0
    plausibility_level: str = "LOW"
    last_updated_at: str = ""


@dataclass
class FaceMeta:
    face_id: str
    label: str = ""
    created_at: str = ""
    last_accessed: str = ""
    occupancy: int = 0
    file_count: int = 0
    status: str = "available"
    selector: str = ""
    credentials_initialized: bool = False
    object_binding_initialized: bool = False
    dummy_profile: DummyProfileMeta = field(default_factory=DummyProfileMeta)


@dataclass
class VesselMeta:
    path: Path
    name: str = ""
    size_bytes: int = 0
    header_status: str = "absent"
    magic_bytes_status: str = "absent"
    face_count: int = 0
    posture: VesselPosture = VesselPosture.UNKNOWN
    label: str = ""
    face_labels: list[str] = field(default_factory=list)
    faces: list[FaceMeta] = field(default_factory=list)
    is_open: bool = False
    open_count: int = 0
    last_opened_at: str = ""
    last_closed_at: str = ""
    dummy_profile: DummyProfileMeta = field(default_factory=DummyProfileMeta)

    def __post_init__(self):
        if not self.name:
            self.name = Path(self.path).name

    @property
    def size_human(self) -> str:
        b: float = float(self.size_bytes)
        for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
            if b < 1024:
                return f"{b:.0f} {unit}" if unit == "B" else f"{b:.1f} {unit}"
            b /= 1024
        return f"{b:.1f} PiB"
