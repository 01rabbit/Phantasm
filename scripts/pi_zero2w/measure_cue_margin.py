#!/usr/bin/env python3
"""How much margin a bound access object actually has, on this device.

The cue either matches or it does not, and both the WebUI badge and
`/status` report only that. On stage that is the wrong resolution: an object
scoring 19 against a threshold of 18 and an object scoring 60 look identical
right up until the lighting changes, and then only one of them still opens.
This reports the distance to the threshold, so a comfortable margin can be
told apart from one that happens to be passing today.

Reads the same reference store the console uses. Registers nothing, writes
nothing, changes nothing.

Usage, from the repository root on the device, with the object presented:

    .venv/bin/python scripts/pi_zero2w/measure_cue_margin.py
    .venv/bin/python scripts/pi_zero2w/measure_cue_margin.py --frames 60

Stop the operator console first — the camera is exclusive.

Reading the result:

  * A worst-case margin under about x1.5 is where stage lighting bites.
  * Prefer moving the object closer, or choosing one with more texture, over
    lowering the ratios: a template with more keypoints raises the threshold
    and the score together, and the score rises faster.
  * Under roughly 48 keypoints the floors bind rather than the ratios, and
    `PHASMID_CUE_GOOD_MATCH_RATIO` / `PHASMID_CUE_INLIER_RATIO` will not move
    the bar at all. The script says so when it happens.
  * If the ratios are lowered, re-run this with the object absent and with an
    unbound object. Confirming only the side that should match confirms
    nothing.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from phasmid.ai_gate import AIGate  # noqa: E402

#: Below this the reported worst case is close enough to the threshold that a
#: lighting change on the day can cross it. Judgement, not a measured cliff.
COMFORTABLE_MARGIN = 1.5

#: Keypoint count below which `GOOD_MATCH_FLOOR` rather than the ratio decides
#: the threshold, computed from the shipped defaults (12 / 0.25).
FLOOR_BINDS_BELOW = 48


def raw_scores(matcher, ref_state, frame_gray):
    """Good matches and RANSAC inliers for one frame, without the cutoffs.

    `match_reference_state` returns `None` for anything below threshold, which
    collapses "scored 17, needed 19" and "scored nothing at all" into the same
    answer. Those two ask for opposite fixes — one wants a nudge, the other a
    different object — so they are scored apart here.

    Returns `(frame descriptors, good matches, inliers)`.
    """
    ref_des, ref_kp = ref_state["des"], ref_state["kp"]
    if ref_des is None or ref_kp is None or frame_gray is None:
        return None

    kp, des = matcher.orb.detectAndCompute(frame_gray, None)
    if des is None:
        return (0, 0, 0)

    good = []
    for pair in matcher.bf.knnMatch(ref_des, des, k=2):
        if len(pair) < 2:
            continue
        candidate, runner_up = pair
        if candidate.distance < 0.75 * runner_up.distance:
            good.append(candidate)

    # findHomography needs four correspondences before it can fit anything.
    if len(good) < 4:
        return (len(des), len(good), 0)

    src = np.float32([ref_kp[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst = np.float32([kp[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    _homography, mask = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)
    inliers = 0 if mask is None else int(mask.ravel().tolist().count(1))
    return (len(des), len(good), inliers)


def report_thresholds(gate) -> list:
    """Print the bar each bound entry has to clear, and why it is that number."""
    matcher = gate.matcher
    print(
        f"ratios : good={matcher.min_good_match_ratio}  inliers={matcher.min_inlier_ratio}"
    )
    print(f"floors : good={matcher.GOOD_MATCH_FLOOR}  inliers={matcher.INLIER_FLOOR}")
    print(f"caps   : good={matcher.min_good_matches}  inliers={matcher.min_inliers}")
    print("thresholds are exclusive: a frame has to score MORE than the number shown")
    print()

    bound = []
    for mode in gate.MODES:
        state = gate.reference_data.get(mode) or {}
        keypoints = state.get("kp")
        if not keypoints:
            print(f"  entry {mode:<10} not bound")
            continue
        good_bar, inlier_bar = matcher.effective_thresholds(state)
        print(
            f"  entry {mode:<10} keypoints={len(keypoints):<5} "
            f"needs good>{good_bar}  inliers>{inlier_bar}   "
            f"(good bar is {good_bar / len(keypoints):.0%} of the template)"
        )
        if len(keypoints) < FLOOR_BINDS_BELOW:
            print(
                "               ^ under ~48 keypoints the FLOOR sets this bar, not\n"
                "                 the ratio. Lowering the ratio will not move it;\n"
                "                 a bigger or more textured object will."
            )
        bound.append((mode, state, good_bar, inlier_bar))
    return bound


def sample(gate, bound, frames: int, settle: float) -> dict:
    """Score `frames` live frames against every bound template."""
    matcher = gate.matcher
    tallies: dict[str, list] = {mode: [] for mode, _, _, _ in bound}

    gate.camera.open()
    time.sleep(settle)
    try:
        for index in range(frames):
            frame = gate.camera.read()
            if frame is None:
                print(f"  {index:>3}  no frame from the camera")
                time.sleep(0.25)
                continue
            gray = matcher.to_gray(frame)
            cells = []
            for mode, state, good_bar, inlier_bar in bound:
                scored = raw_scores(matcher, state, gray)
                if scored is None:
                    cells.append(f"{mode}: -")
                    tallies[mode].append(None)
                    continue
                _descriptors, good, inliers = scored
                matched = good > good_bar and inliers > inlier_bar
                cells.append(
                    f"{mode}: {'MATCH' if matched else 'miss '} "
                    f"good={good:>3}/{good_bar:<3} inliers={inliers:>3}/{inlier_bar:<3}"
                )
                tallies[mode].append((good, inliers) if matched else None)
            print(f"  {index:>3}  " + "   ".join(cells))
            time.sleep(0.2)
    finally:
        gate.camera.close()
    return tallies


def summarise(bound, tallies) -> None:
    print()
    for mode, _state, good_bar, inlier_bar in bound:
        hits = [t for t in tallies[mode] if t]
        total = len(tallies[mode])
        rate = len(hits) / max(1, total)
        print(f"entry {mode}: matched {len(hits)}/{total} frames ({rate:.0%})")
        if not hits:
            print(
                "   never matched — the object is absent, unbound, or unrecognisable here"
            )
            continue
        goods = sorted(good for good, _ in hits)
        inliers = sorted(count for _, count in hits)
        good_margin = goods[0] / max(1, good_bar)
        inlier_margin = inliers[0] / max(1, inlier_bar)
        print(
            f"   good    min={goods[0]:<4} median={goods[len(goods) // 2]:<4} "
            f"max={goods[-1]:<4} worst-case margin x{good_margin:.1f}"
        )
        print(
            f"   inliers min={inliers[0]:<4} median={inliers[len(inliers) // 2]:<4} "
            f"max={inliers[-1]:<4} worst-case margin x{inlier_margin:.1f}"
        )
        if rate < 1.0:
            print(
                "   ! not every frame matched — presentation is unstable, not marginal"
            )
        if min(good_margin, inlier_margin) < COMFORTABLE_MARGIN:
            print(
                f"   ! worst case is under x{COMFORTABLE_MARGIN} — expect this to fail on stage"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--frames", type=int, default=20, help="frames to sample (default 20)"
    )
    parser.add_argument(
        "--settle",
        type=float,
        default=1.0,
        help="seconds to let the camera settle before sampling (default 1.0)",
    )
    args = parser.parse_args()

    gate = AIGate()
    bound = report_thresholds(gate)
    if not bound:
        print("\nNothing is bound to an object yet. Register one first, then re-run.")
        return 1

    print(f"\nPresent the object. Sampling {args.frames} frames...\n")
    tallies = sample(gate, bound, args.frames, args.settle)
    summarise(bound, tallies)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
