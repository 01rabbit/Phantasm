#!/usr/bin/env python3
"""Find the camera settings that give this object the most to match on.

The cue is built out of ORB keypoints, and how many the camera delivers is
decided long before any threshold is applied: by resolution, by how long the
shutter is open, by how hard the ISP denoises, and by where the lens is. Those
were all left at defaults tuned for photographs a person will look at, which is
not the same thing as an image a corner detector can work with.

The right values depend on the room and the object, not on anything that can be
decided in advance. So this sweeps them against the object actually in front of
the camera and reports what each one is worth.

Run ON the device, from the repository root, with the operator console stopped
and **the object sitting in front of the camera, not moving**:

    .venv/bin/python scripts/pi_zero2w/tune_camera.py

It changes nothing. It prints an export line to put in front of
`run_demo_console.sh` if the sweep finds something better than the defaults -
and it will not recommend a setting the device cannot keep up with, however
well that setting scores.

Two numbers per configuration:

  keypoints  what ORB finds in the whole frame, counted with the detector's
             cap lifted so the number keeps meaning something past the point
             the gate itself stops at. More is more to match on, and this is
             what decides whether an object can be bound at all - a template
             needs 60 of its own.
  sharpness  variance of the Laplacian: how much fine detail survives to be
             found. Falls with blur, whether from a lens in the wrong place or
             a shutter open too long. Useful as the reason a keypoint count
             moved.
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys
import time
from pathlib import Path

os.environ.setdefault("LIBCAMERA_LOG_LEVELS", "*:ERROR")

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

import cv2  # noqa: E402

from phasmid.camera_frame_source import CameraFrameSource  # noqa: E402
from phasmid.object_cue_matcher import ObjectCueMatcher  # noqa: E402

#: Sampled per configuration. Enough to median away a single bad frame without
#: making the whole sweep something nobody waits for.
FRAMES_PER_SETTING = 6

MATCHER = ObjectCueMatcher(
    min_reference_keypoints=60,
    min_frame_descriptors=10,
    min_good_matches=50,
    min_inliers=30,
)

#: The gate's detector stops at `nfeatures=1000`, which is the right cap for
#: matching and the wrong one for comparing settings: past a certain amount of
#: detail every configuration reports exactly 1000 and the sweep can no longer
#: tell them apart. Measured on the device, 640x480 gave 919 and everything
#: above it gave 1000 - which reads as "bigger is better" when it is really
#: "the ruler ended here". So the probe counts with the cap lifted.
PROBE = cv2.ORB_create(nfeatures=20000)

#: How much of the frame interval the sweep's own work may take. The console
#: does more per frame than this does - it matches against every bound entry,
#: encodes a JPEG and draws the overlay - so a configuration that only just
#: fits here will not fit there. At the console's four frames a second the
#: interval is 250 ms; this leaves room for the rest of the pipeline.
FRAME_BUDGET_MS = 150.0


def measure(size: tuple[int, int], env: dict[str, str], settle: float = 1.5) -> dict:
    """Open the camera under `env` and report what it delivers."""
    previous = {key: os.environ.get(key) for key in env}
    os.environ.update(env)
    os.environ["PHASMID_CAMERA_SIZE"] = f"{size[0]}x{size[1]}"

    camera = CameraFrameSource(frame_size=size, fps=4)
    keypoints: list[int] = []
    sharpness: list[float] = []
    intervals: list[float] = []
    try:
        camera.open()
        time.sleep(settle)
        last = time.perf_counter()
        for _ in range(FRAMES_PER_SETTING):
            success, frame = camera.read()
            now = time.perf_counter()
            intervals.append(now - last)
            last = now
            if not success or frame is None:
                continue
            gray = MATCHER.to_gray(frame)
            found = PROBE.detect(gray, None)
            keypoints.append(len(found) if found else 0)
            sharpness.append(float(cv2.Laplacian(gray, cv2.CV_64F).var()))
        applied = camera.status()
    finally:
        camera.close()
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    return {
        "keypoints": int(statistics.median(keypoints)) if keypoints else 0,
        "sharpness": statistics.median(sharpness) if sharpness else 0.0,
        "interval_ms": statistics.median(intervals) * 1000 if intervals else 0.0,
        "focus": applied.get("focus_mode"),
        "applied": applied.get("applied_controls", []),
    }


class CameraDeliveredNothing(RuntimeError):
    """No configuration produced a single keypoint."""


def show(label: str, result: dict) -> None:
    print(
        f"  {label:<26} keypoints {result['keypoints']:>5}"
        f"   sharpness {result['sharpness']:>8.1f}"
        f"   {result['interval_ms']:>6.0f} ms/frame"
    )


def sweep(title: str, options: list, run) -> tuple:
    """Try each option and return the best one the device can actually run.

    Two things this must not do, both learned from a run that did them:

    Recommend a configuration the console cannot keep up with. More pixels than
    the device can process is not more cue - the match history needs several
    consecutive frames, and frames that arrive late are frames that do not
    arrive. So anything past the budget is out, however well it scores.

    Pick a winner out of a tie. When several options report the same keypoint
    count the difference is below what this can measure, and `max` would answer
    with whichever happened to be first in the list. Ties fall through to
    sharpness, and if that is level too, to the cheapest.
    """
    print(f"\n{title}")
    scored = []
    for label, option in options:
        result = run(option)
        show(label, result)
        scored.append((label, option, result))

    if not any(row[2]["keypoints"] for row in scored):
        # Not a tie - a camera that is not delivering. A recommendation
        # computed from zeros would be worse than none.
        raise CameraDeliveredNothing(title)

    affordable = [row for row in scored if row[2]["interval_ms"] <= FRAME_BUDGET_MS]
    if not affordable:
        cheapest = min(scored, key=lambda row: row[2]["interval_ms"])
        print(
            f"  ! every option costs more than {FRAME_BUDGET_MS:.0f} ms/frame; "
            f"falling back to the cheapest ({cheapest[0]})"
        )
        affordable = [cheapest]
    elif len(affordable) < len(scored):
        dropped = [row[0] for row in scored if row not in affordable]
        print(f"  ! too slow for the console, not considered: {', '.join(dropped)}")

    best = max(
        affordable,
        key=lambda row: (
            row[2]["keypoints"],
            row[2]["sharpness"],
            -row[2]["interval_ms"],
        ),
    )
    tied = [row[0] for row in affordable if row[2]["keypoints"] == best[2]["keypoints"]]
    if len(tied) > 1:
        print(f"  ({len(tied)} tied on keypoints; broken by sharpness)")
    print(f"  -> best: {best[0]}")
    return best[1], best[2]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--quick",
        action="store_true",
        help="resolution and exposure only, for when the bench is short of time",
    )
    args = parser.parse_args()

    print("Put the object in front of the camera and leave it there.")
    print("Nothing here is written anywhere; the console should be stopped.\n")

    baseline = {
        "PHASMID_CAMERA_MAX_EXPOSURE_US": "33000",
        "PHASMID_CAMERA_DENOISE": "minimal",
        "PHASMID_CAMERA_SHARPNESS": "1.5",
    }

    first = measure((640, 480), baseline)
    print(f"focus reported as: {first['focus']}")
    print(f"controls the camera accepted: {', '.join(first['applied']) or 'none'}")
    if first["focus"] in {"fixed lens", "unavailable"}:
        print("\n! This module has no lens to move. Focus it by hand before tuning.")

    size, _ = sweep(
        "RESOLUTION — how many pixels the object gets",
        [(f"{w}x{h}", (w, h)) for w, h in ((640, 480), (1024, 768), (1280, 960))],
        lambda option: measure(option, baseline),
    )

    exposure, _ = sweep(
        "SHUTTER CEILING — blur against noise",
        [
            ("16 ms (sharp, noisy)", "16000"),
            ("33 ms (default)", "33000"),
            ("66 ms", "66000"),
            ("200 ms (the old value)", "200000"),
        ],
        lambda option: measure(
            size, {**baseline, "PHASMID_CAMERA_MAX_EXPOSURE_US": option}
        ),
    )
    settings = {**baseline, "PHASMID_CAMERA_MAX_EXPOSURE_US": exposure}

    if not args.quick:
        denoise, _ = sweep(
            "DENOISE — smoothing removes what ORB looks for",
            [
                ("off", "off"),
                ("minimal (default)", "minimal"),
                ("the ISP's own", "fast"),
            ],
            lambda option: measure(
                size, {**settings, "PHASMID_CAMERA_DENOISE": option}
            ),
        )
        settings["PHASMID_CAMERA_DENOISE"] = denoise

        sharpness, _ = sweep(
            "SHARPNESS — edge contrast is what FAST measures",
            [("1.0 (camera default)", "1.0"), ("1.5 (default)", "1.5"), ("2.5", "2.5")],
            lambda option: measure(
                size, {**settings, "PHASMID_CAMERA_SHARPNESS": option}
            ),
        )
        settings["PHASMID_CAMERA_SHARPNESS"] = sharpness

    print("\n" + "=" * 66)
    print("Put this in front of the console launcher:\n")
    print(
        f"  PHASMID_CAMERA_SIZE={size[0]}x{size[1]} \\\n"
        f"  PHASMID_CAMERA_MAX_EXPOSURE_US={settings['PHASMID_CAMERA_MAX_EXPOSURE_US']} \\\n"
        f"  PHASMID_CAMERA_DENOISE={settings['PHASMID_CAMERA_DENOISE']} \\\n"
        f"  PHASMID_CAMERA_SHARPNESS={settings['PHASMID_CAMERA_SHARPNESS']} \\\n"
        f"    bash scripts/pi_zero2w/run_demo_console.sh"
    )
    print(
        "\nHigher resolution costs frame time. If ms/frame above went past about\n"
        "250, the console will not hold four frames a second, and the match\n"
        "history needs several frames in a row - so take the step down."
    )
    print(
        "Then re-bind the object and check the margin with\n"
        "  .venv/bin/python scripts/pi_zero2w/measure_cue_margin.py --frames 30"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CameraDeliveredNothing as failure:
        print(
            f"\nNo frame produced a single keypoint during: {failure}\n"
            "The camera is not delivering usable frames, so there is nothing to\n"
            "tune. Check that the console is stopped (the camera is exclusive),\n"
            "that the module is attached, and that something is in front of it."
        )
        raise SystemExit(1) from None
