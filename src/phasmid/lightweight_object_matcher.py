"""
Evaluation/benchmark component - not wired into runtime.

Lightweight object matcher supporting ORB and AKAZE feature detectors.

Both detectors use binary descriptors matched with BFMatcher(NORM_HAMMING).
AKAZE is evaluated as a candidate alternative to ORB for constrained hardware:
it tends to produce fewer but more stable keypoints at the cost of slightly
higher per-frame CPU time.

This module is an evaluation component.  It is not a direct replacement for
:class:`~phasmid.object_cue_matcher.ObjectCueMatcher` and must never produce
or influence cryptographic key material.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, cast

import cv2
import numpy as np

Algo = Literal["orb", "akaze"]


@dataclass(frozen=True)
class ObjectMatchResult:
    """Neutral per-frame match result.  Not cryptographic material."""

    matched: bool
    inliers: int
    confidence: float  # 0.0–1.0; based on inlier count relative to threshold
    status: str  # "no_reference" | "no_descriptors" | "low_inliers" | "accepted"
    algo: Algo


class LightweightObjectMatcher:
    """
    Feature-based object matcher with selectable ORB or AKAZE backend.

    Usage pattern:
      1. Call :meth:`enroll_reference` with a BGR frame of the target object.
      2. Call :meth:`match` for each query frame.

    AKAZE notes:
    - Descriptor type DESCRIPTOR_MLDB (default) is binary → compatible with
      NORM_HAMMING, same as ORB.
    - Typically generates 200–600 keypoints on a 320×240 frame vs.
      ORB's ~500–1000.  Fewer but more geometrically stable.
    - Slightly slower per frame than ORB on Pi Zero 2 W due to float-domain
      scale-space construction.

    ORB notes:
    - Fast binary descriptor; well-suited for low-CPU budgets.
    - Already used in production :class:`~phasmid.object_cue_matcher.ObjectCueMatcher`.
    """

    # Shared defaults; callers may override per instance.
    DEFAULT_MAX_FEATURES: int = 500
    DEFAULT_MIN_REFERENCE_KP: int = 40
    DEFAULT_MIN_FRAME_DESCRIPTORS: int = 10
    DEFAULT_MIN_GOOD_MATCHES: int = 20
    DEFAULT_MIN_INLIERS: int = 12
    LOWE_RATIO: float = 0.75
    RANSAC_THRESHOLD: float = 5.0

    def __init__(
        self,
        algo: Algo = "orb",
        *,
        max_features: int = DEFAULT_MAX_FEATURES,
        min_reference_kp: int = DEFAULT_MIN_REFERENCE_KP,
        min_frame_descriptors: int = DEFAULT_MIN_FRAME_DESCRIPTORS,
        min_good_matches: int = DEFAULT_MIN_GOOD_MATCHES,
        min_inliers: int = DEFAULT_MIN_INLIERS,
    ) -> None:
        self.algo: Algo = algo
        self.min_reference_kp = min_reference_kp
        self.min_frame_descriptors = min_frame_descriptors
        self.min_good_matches = min_good_matches
        self.min_inliers = min_inliers

        cv2_any = cast(Any, cv2)
        if algo == "orb":
            self._detector: Any = cv2_any.ORB_create(nfeatures=max_features)
        else:
            self._detector = cv2_any.AKAZE_create()

        self._bf = cv2.BFMatcher(cv2.NORM_HAMMING)
        self._ref_kp: list[cv2.KeyPoint] | None = None
        self._ref_des: np.ndarray | None = None
        self._ref_shape: tuple[int, int] | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def enroll_reference(self, frame: np.ndarray) -> bool:
        """
        Extract and store keypoints from *frame* as the reference object.
        Returns True if enough keypoints were found.
        """
        gray = self._to_gray(frame)
        kp, des = self._detector.detectAndCompute(gray, None)
        if not kp or des is None or len(kp) < self.min_reference_kp:
            return False
        self._ref_kp = list(kp)
        self._ref_des = des
        self._ref_shape = gray.shape  # (h, w)
        return True

    def match(self, frame: np.ndarray) -> ObjectMatchResult:
        """
        Match *frame* against the enrolled reference.
        Returns a :class:`ObjectMatchResult` with a neutral status.
        """
        if self._ref_des is None or self._ref_kp is None:
            return self._result(False, 0, "no_reference")

        gray = self._to_gray(frame)
        kp, des = self._detector.detectAndCompute(gray, None)
        if des is None or len(des) <= self.min_frame_descriptors:
            return self._result(False, 0, "no_descriptors")

        good = self._lowe_ratio_filter(self._ref_des, des)
        if len(good) <= self.min_good_matches:
            return self._result(False, len(good), "low_inliers")

        inliers = self._ransac_inliers(self._ref_kp, kp, good)
        if inliers is None or inliers <= self.min_inliers:
            return self._result(False, inliers or 0, "low_inliers")

        return self._result(True, inliers, "accepted")

    def clear(self) -> None:
        self._ref_kp = None
        self._ref_des = None
        self._ref_shape = None

    @property
    def is_enrolled(self) -> bool:
        return self._ref_des is not None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _to_gray(self, frame: np.ndarray) -> np.ndarray:
        return cv2.equalizeHist(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))

    def _lowe_ratio_filter(
        self, ref_des: np.ndarray, frame_des: np.ndarray
    ) -> list[cv2.DMatch]:
        matches = self._bf.knnMatch(ref_des, frame_des, k=2)
        good: list[cv2.DMatch] = []
        for pair in matches:
            if len(pair) < 2:
                continue
            m, n = pair
            if m.distance < self.LOWE_RATIO * n.distance:
                good.append(m)
        return good

    def _ransac_inliers(
        self,
        ref_kp: list[cv2.KeyPoint],
        frame_kp: list[cv2.KeyPoint],
        good_matches: list[cv2.DMatch],
    ) -> int | None:
        src: Any = np.array(
            [ref_kp[m.queryIdx].pt for m in good_matches], dtype=np.float32
        ).reshape(-1, 1, 2)
        dst: Any = np.array(
            [frame_kp[m.trainIdx].pt for m in good_matches], dtype=np.float32
        ).reshape(-1, 1, 2)
        _, mask = cv2.findHomography(src, dst, cv2.RANSAC, self.RANSAC_THRESHOLD)
        if mask is None:
            return None
        return int(mask.ravel().tolist().count(1))

    def _result(self, matched: bool, inliers: int, status: str) -> ObjectMatchResult:
        confidence = min(1.0, inliers / max(self.min_inliers, 1)) if matched else 0.0
        return ObjectMatchResult(
            matched=matched,
            inliers=inliers,
            confidence=float(confidence),
            status=status,
            algo=self.algo,
        )
