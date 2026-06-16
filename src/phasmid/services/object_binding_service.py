from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from ..config import allow_no_object_binding


@dataclass(frozen=True)
class ObjectBindingProfile:
    source_type: str
    average_hash: str
    edge_hash: str
    brightness_histogram: list[float]
    color_histogram: list[float]
    threshold: float
    fingerprint_id: str
    updated_at: str

    def to_record(self) -> dict[str, object]:
        return {
            "source_type": self.source_type,
            "average_hash": self.average_hash,
            "edge_hash": self.edge_hash,
            "brightness_histogram": list(self.brightness_histogram),
            "color_histogram": list(self.color_histogram),
            "threshold": self.threshold,
            "fingerprint_id": self.fingerprint_id,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class ObjectBindingMatch:
    matched: bool
    similarity: float
    threshold: float


class ObjectBindingService:
    _AVERAGE_HASH_SIZE = 8
    _EDGE_HASH_SIZE = 8
    _BRIGHTNESS_BINS = 16
    _COLOR_BINS = 8
    _IMAGE_THRESHOLD = 0.98
    _CAMERA_THRESHOLD = 0.78

    def profile_from_image_path(self, path: str | Path) -> ObjectBindingProfile:
        image_path = Path(path).expanduser().resolve()
        if not image_path.is_file():
            raise FileNotFoundError(f"object source unavailable: {image_path}")
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"object source unavailable: could not read {image_path}")
        return self.profile_from_image(image, source_type="image_file")

    def profile_from_frame(self, frame: np.ndarray) -> ObjectBindingProfile:
        return self.profile_from_image(frame, source_type="camera")

    def profile_from_image(
        self, image: np.ndarray, source_type: str = "image_file"
    ) -> ObjectBindingProfile:
        if image is None or image.size == 0:
            raise ValueError("object source unavailable: empty image")

        prepared = self._prepare_color(image)
        gray = cv2.cvtColor(prepared, cv2.COLOR_BGR2GRAY)
        average_hash = self._average_hash(gray)
        edge_hash = self._edge_hash(gray)
        brightness_histogram = self._brightness_histogram(gray)
        color_histogram = self._color_histogram(prepared)
        fingerprint_bytes = "|".join(
            [
                average_hash,
                edge_hash,
                ",".join(f"{value:.6f}" for value in brightness_histogram),
                ",".join(f"{value:.6f}" for value in color_histogram),
            ]
        ).encode("utf-8")
        fingerprint_id = hashlib.sha256(fingerprint_bytes).hexdigest()
        threshold = (
            self._CAMERA_THRESHOLD
            if source_type == "camera"
            else self._IMAGE_THRESHOLD
        )
        return ObjectBindingProfile(
            source_type=source_type,
            average_hash=average_hash,
            edge_hash=edge_hash,
            brightness_histogram=brightness_histogram,
            color_histogram=color_histogram,
            threshold=threshold,
            fingerprint_id=fingerprint_id,
            updated_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )

    def disabled_record(self) -> dict[str, object]:
        return {
            "source_type": "disabled",
            "average_hash": "",
            "edge_hash": "",
            "brightness_histogram": [],
            "color_histogram": [],
            "threshold": 0.0,
            "fingerprint_id": "",
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

    def normalize_record(self, value: object) -> dict[str, object]:
        if not isinstance(value, dict):
            return {}
        return {
            "source_type": str(value.get("source_type", "")),
            "average_hash": str(value.get("average_hash", "")),
            "edge_hash": str(value.get("edge_hash", "")),
            "brightness_histogram": self._float_list(
                value.get("brightness_histogram", [])
            ),
            "color_histogram": self._float_list(value.get("color_histogram", [])),
            "threshold": self._float_value(value.get("threshold", 0.0)),
            "fingerprint_id": str(value.get("fingerprint_id", "")),
            "updated_at": str(value.get("updated_at", "")),
        }

    def match(
        self,
        stored_record: dict[str, object],
        candidate: ObjectBindingProfile,
        *,
        tolerant: bool | None = None,
    ) -> ObjectBindingMatch:
        stored = self.normalize_record(stored_record)
        if not stored:
            return ObjectBindingMatch(matched=False, similarity=0.0, threshold=1.0)
        if str(stored.get("source_type", "")) == "disabled":
            return ObjectBindingMatch(matched=False, similarity=0.0, threshold=1.0)

        average_similarity = self._hash_similarity(
            str(stored.get("average_hash", "")),
            candidate.average_hash,
        )
        edge_similarity = self._hash_similarity(
            str(stored.get("edge_hash", "")),
            candidate.edge_hash,
        )
        brightness_similarity = self._histogram_similarity(
            self._float_list(stored.get("brightness_histogram", [])),
            candidate.brightness_histogram,
        )
        color_similarity = self._histogram_similarity(
            self._float_list(stored.get("color_histogram", [])),
            candidate.color_histogram,
        )
        similarity = (
            0.45 * average_similarity
            + 0.25 * edge_similarity
            + 0.15 * brightness_similarity
            + 0.15 * color_similarity
        )
        threshold = self._float_value(stored.get("threshold", candidate.threshold))
        if tolerant is True:
            threshold = min(threshold, self._CAMERA_THRESHOLD)
        elif tolerant is False:
            threshold = max(threshold, self._IMAGE_THRESHOLD)
        return ObjectBindingMatch(
            matched=similarity >= threshold,
            similarity=similarity,
            threshold=threshold,
        )

    def no_object_binding_allowed(self) -> bool:
        return allow_no_object_binding()

    def _prepare_color(self, image: np.ndarray) -> np.ndarray:
        if image.ndim == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        return cv2.resize(image, (64, 64), interpolation=cv2.INTER_AREA)

    def _average_hash(self, gray: np.ndarray) -> str:
        resized = cv2.resize(
            gray,
            (self._AVERAGE_HASH_SIZE, self._AVERAGE_HASH_SIZE),
            interpolation=cv2.INTER_AREA,
        )
        mean_value = float(resized.mean())
        bits = resized >= mean_value
        return "".join("1" if value else "0" for value in bits.flatten())

    def _edge_hash(self, gray: np.ndarray) -> str:
        edges = cv2.Canny(gray, 40, 120)
        resized = cv2.resize(
            edges,
            (self._EDGE_HASH_SIZE, self._EDGE_HASH_SIZE),
            interpolation=cv2.INTER_AREA,
        )
        bits = resized >= 32
        return "".join("1" if value else "0" for value in bits.flatten())

    def _brightness_histogram(self, gray: np.ndarray) -> list[float]:
        hist, _ = np.histogram(gray, bins=self._BRIGHTNESS_BINS, range=(0, 256))
        return self._normalize_histogram(hist)

    def _color_histogram(self, image: np.ndarray) -> list[float]:
        channels = cv2.split(image)
        values: list[float] = []
        for channel in channels:
            hist, _ = np.histogram(channel, bins=self._COLOR_BINS, range=(0, 256))
            values.extend(self._normalize_histogram(hist))
        return [round(value, 6) for value in values]

    def _normalize_histogram(self, values: np.ndarray) -> list[float]:
        total = float(values.sum())
        if total <= 0:
            return [0.0 for _value in values]
        return [round(float(value) / total, 6) for value in values]

    def _hash_similarity(self, left: str, right: str) -> float:
        if not left or not right or len(left) != len(right):
            return 0.0
        mismatches = sum(
            1
            for left_bit, right_bit in zip(left, right, strict=True)
            if left_bit != right_bit
        )
        return 1.0 - (mismatches / float(len(left)))

    def _histogram_similarity(
        self, left: list[float], right: list[float]
    ) -> float:
        if not left or not right or len(left) != len(right):
            return 0.0
        return float(sum(min(a, b) for a, b in zip(left, right, strict=True)))

    def _float_list(self, value: object) -> list[float]:
        if not isinstance(value, list):
            return []
        result: list[float] = []
        for item in value:
            result.append(self._float_value(item))
        return result

    def _float_value(self, value: object) -> float:
        if isinstance(value, bool):
            return float(int(value))
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, (str, bytes, bytearray)):
            try:
                return float(value)
            except ValueError:
                return 0.0
        return 0.0
