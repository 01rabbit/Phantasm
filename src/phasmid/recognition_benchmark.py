"""
Evaluation/benchmark component - not wired into runtime.

Offline benchmark harness for object recognition evaluation (Issue #38).

No camera is required.  Callers supply pre-captured BGR frames (numpy arrays).
The harness measures per-frame latency, produces accept/reject statistics, and
summarises findings suitable for recording in a field-test validation document.

All outputs are neutral status labels and numeric scores.  Nothing here
produces or influences cryptographic key material.

Intended workflow:
  1. Collect frames on target hardware (e.g. Raspberry Pi Zero 2 W).
  2. Save frames to disk (e.g. as .npy or JPEG).
  3. Load frames on any machine and run the benchmark.
  4. Record BenchmarkSummary values in the review validation record.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from .lightweight_object_matcher import LightweightObjectMatcher, ObjectMatchResult


@dataclass
class ObjectBenchmarkSummary:
    """Aggregated object feature-matching benchmark result."""

    algo: str
    n_probe_frames: int
    enroll_ok: bool
    accept_count: int
    reject_count: int
    no_descriptor_count: int
    latency_ms_mean: float
    latency_ms_p50: float
    latency_ms_p95: float
    inliers_mean: float
    inliers_p50: float
    confidence_mean: float
    notes: str = ""

    @property
    def accept_rate(self) -> float:
        total = self.accept_count + self.reject_count + self.no_descriptor_count
        return self.accept_count / total if total else 0.0


@dataclass
class ComparisonReport:
    """Side-by-side comparison of two object matchers (e.g. ORB vs AKAZE)."""

    baseline: ObjectBenchmarkSummary
    candidate: ObjectBenchmarkSummary
    latency_delta_ms: float = field(init=False)
    inliers_delta: float = field(init=False)
    accept_rate_delta: float = field(init=False)

    def __post_init__(self) -> None:
        self.latency_delta_ms = (
            self.candidate.latency_ms_mean - self.baseline.latency_ms_mean
        )
        self.inliers_delta = self.candidate.inliers_mean - self.baseline.inliers_mean
        self.accept_rate_delta = self.candidate.accept_rate - self.baseline.accept_rate

    def recommendation(self) -> str:
        """Neutral recommendation string based on latency and accept-rate delta."""
        latency_ok = self.latency_delta_ms <= 50.0
        accept_ok = self.accept_rate_delta >= -0.05
        if latency_ok and accept_ok:
            return "candidate acceptable: similar or better reliability within latency budget"
        if not latency_ok and accept_ok:
            return "candidate exceeds latency budget; retain baseline unless reliability gain justifies cost"
        if latency_ok and not accept_ok:
            return "candidate accept rate drops more than 5 pp; retain baseline"
        return "candidate is slower and less reliable; retain baseline"


class RecognitionBenchmark:
    """
    Benchmark runner for :class:`LightweightObjectMatcher`.

    All timing is wall-clock (``time.perf_counter``).  On a development
    machine this will be faster than Pi Zero 2 W; the measurements are useful
    for relative comparisons (ORB vs AKAZE, thresholds) and for establishing
    a lower-bound baseline before target-hardware runs.
    """

    def run_object_benchmark(
        self,
        reference_frame: np.ndarray,
        probe_frames: list[np.ndarray],
        *,
        algo: str = "orb",
        notes: str = "",
    ) -> ObjectBenchmarkSummary:
        """
        Enroll from *reference_frame*, then match each *probe_frame*.

        All probe frames are expected to contain the reference object (positive
        probes).
        """

        matcher = LightweightObjectMatcher(algo=algo)  # type: ignore[arg-type]
        enroll_ok = matcher.enroll_reference(reference_frame)

        latencies: list[float] = []
        results: list[ObjectMatchResult] = []

        for frame in probe_frames:
            t0 = time.perf_counter()
            result = matcher.match(frame)
            latencies.append((time.perf_counter() - t0) * 1000.0)
            results.append(result)

        accept = sum(1 for r in results if r.matched)
        no_desc = sum(1 for r in results if r.status == "no_descriptors")
        reject = len(results) - accept - no_desc
        inliers_all = [r.inliers for r in results]
        confidences = [r.confidence for r in results]

        return ObjectBenchmarkSummary(
            algo=algo,
            n_probe_frames=len(probe_frames),
            enroll_ok=enroll_ok,
            accept_count=accept,
            reject_count=reject,
            no_descriptor_count=no_desc,
            latency_ms_mean=float(np.mean(latencies)) if latencies else 0.0,
            latency_ms_p50=float(np.percentile(latencies, 50)) if latencies else 0.0,
            latency_ms_p95=float(np.percentile(latencies, 95)) if latencies else 0.0,
            inliers_mean=float(np.mean(inliers_all)) if inliers_all else 0.0,
            inliers_p50=float(np.percentile(inliers_all, 50)) if inliers_all else 0.0,
            confidence_mean=float(np.mean(confidences)) if confidences else 0.0,
            notes=notes,
        )

    def compare_object_algos(
        self,
        reference_frame: np.ndarray,
        probe_frames: list[np.ndarray],
        *,
        baseline_algo: str = "orb",
        candidate_algo: str = "akaze",
    ) -> ComparisonReport:
        """Run both algos and return a side-by-side :class:`ComparisonReport`."""
        baseline = self.run_object_benchmark(
            reference_frame,
            probe_frames,
            algo=baseline_algo,
            notes=f"baseline ({baseline_algo})",
        )
        candidate = self.run_object_benchmark(
            reference_frame,
            probe_frames,
            algo=candidate_algo,
            notes=f"candidate ({candidate_algo})",
        )
        return ComparisonReport(baseline=baseline, candidate=candidate)
