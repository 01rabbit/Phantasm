from __future__ import annotations

from typing import Any, cast

import cv2
import numpy as np


class ObjectCueMatcher:
    """ORB-based object-cue matching isolated from camera and UI concerns."""

    # Per-pixel intensity change, on unequalised grayscale, that counts as "this
    # part of the frame is not the scene any more". Low enough to catch a matte
    # object against a similar-toned background, high enough to ignore sensor
    # noise and the small exposure drift between two consecutive frames.
    OBJECT_MASK_THRESHOLD = 30

    # The masked region has to look like something placed in the scene. Below
    # the floor there is nothing to describe; above the ceiling the whole view
    # changed, which means the camera moved or the lighting did, and the diff no
    # longer isolates an object.
    MIN_OBJECT_AREA_RATIO = 0.01
    MAX_OBJECT_AREA_RATIO = 0.60

    # `min_good_matches` / `min_inliers` are absolute counts calibrated when a
    # reference template covered the whole frame and carried 400-900 keypoints.
    # Masking the template to the object leaves far fewer - 72 on a plain wall -
    # and the same absolute counts then demand that most of the template be
    # re-found exactly. Measured on a 72-keypoint template: the identical frame
    # scores 62 good matches against a floor of 50, and adding +-6 of grayscale
    # noise - less than a real sensor produces - drops it to 42 and the cue
    # refuses an object that is plainly there.
    #
    # So ask for a *proportion* of the template instead, and let the absolute
    # counts stand as a ceiling so nothing ever becomes stricter than before.
    # Discrimination does not depend on the counts being high: it comes from the
    # template describing the object and nothing else. Measured on the same
    # scene, the empty view and a different object each score **zero** good
    # matches, so the separation is 42-vs-0, not 42-vs-49.
    MIN_GOOD_MATCH_RATIO = 0.25
    MIN_INLIER_RATIO = 0.15
    # Floors for a template so small that a proportion means almost nothing.
    GOOD_MATCH_FLOOR = 12
    INLIER_FLOOR = 8

    # How much of the changed area the single largest region has to account for.
    # Something placed in the scene changes one connected region; a scene that
    # moved changes many scattered ones, and its largest region can still be
    # object-sized. Measured: an object held up scores 0.96-1.00, a wholly
    # different view of the same room 0.47. A hand and a cast shadow fragment
    # the change somewhat, so this is set low enough to tolerate that - and
    # when it is too strict the outcome is a visible refusal, not a bad binding.
    MIN_OBJECT_DOMINANCE = 0.60

    # Lowe's ratio test, and the RANSAC reprojection tolerance in pixels. Named
    # so the scoring path and the matching path cannot drift apart: a diagnostic
    # that reports different numbers from the ones the gate acts on is worse
    # than no diagnostic, because it is believed.
    LOWE_RATIO = 0.75
    RANSAC_REPROJECTION = 5.0

    #: Instance overrides for the two above, so a device whose camera or
    #: lighting needs a looser test can have one without every device getting
    #: it. Set from config at construction; the class attributes stay the
    #: shipped defaults.
    lowe_ratio: float
    ransac_reprojection: float

    def __init__(
        self,
        *,
        min_reference_keypoints: int,
        min_frame_descriptors: int,
        min_good_matches: int,
        min_inliers: int,
        object_mask_threshold: int | None = None,
        min_object_area_ratio: float | None = None,
        max_object_area_ratio: float | None = None,
        min_object_dominance: float | None = None,
        min_good_match_ratio: float | None = None,
        min_inlier_ratio: float | None = None,
        lowe_ratio: float | None = None,
        ransac_reprojection: float | None = None,
    ) -> None:
        self.min_reference_keypoints = min_reference_keypoints
        self.min_frame_descriptors = min_frame_descriptors
        self.min_good_matches = min_good_matches
        self.min_inliers = min_inliers
        self.object_mask_threshold = (
            self.OBJECT_MASK_THRESHOLD
            if object_mask_threshold is None
            else object_mask_threshold
        )
        self.min_object_area_ratio = (
            self.MIN_OBJECT_AREA_RATIO
            if min_object_area_ratio is None
            else min_object_area_ratio
        )
        self.max_object_area_ratio = (
            self.MAX_OBJECT_AREA_RATIO
            if max_object_area_ratio is None
            else max_object_area_ratio
        )
        self.min_object_dominance = (
            self.MIN_OBJECT_DOMINANCE
            if min_object_dominance is None
            else min_object_dominance
        )
        self.min_good_match_ratio = (
            self.MIN_GOOD_MATCH_RATIO
            if min_good_match_ratio is None
            else min_good_match_ratio
        )
        self.min_inlier_ratio = (
            self.MIN_INLIER_RATIO if min_inlier_ratio is None else min_inlier_ratio
        )
        self.lowe_ratio = self.LOWE_RATIO if lowe_ratio is None else lowe_ratio
        self.ransac_reprojection = (
            self.RANSAC_REPROJECTION
            if ransac_reprojection is None
            else ransac_reprojection
        )
        self.orb = cast(Any, cv2).ORB_create(nfeatures=1000)
        self.bf = cv2.BFMatcher(cv2.NORM_HAMMING)

    def empty_reference(self) -> dict[str, object | None]:
        return {
            "kp": None,
            "des": None,
            "shape": None,
            "pts": None,
            "path": None,
        }

    def to_gray(self, image):
        """Grayscale as ORB sees it, equalised for contrast."""
        return cv2.equalizeHist(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY))

    def to_diff_gray(self, image):
        """Grayscale for comparing two frames of the same scene.

        Deliberately *not* equalised. `equalizeHist` is a global remap driven by
        the frame's own histogram, so holding an object up changes the mapping
        for every background pixel too, and the difference between the two
        frames stops describing the object. Measured on a mid-tone object
        covering 13.7% of the view: the equalised difference reported 31.3%
        changed, and :meth:`object_mask` refused the capture outright.
        """
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    def _reference_corners(self, h: int, w: int):
        points: Any = [[0, 0], [0, h - 1], [w - 1, h - 1], [w - 1, 0]]
        return cast(Any, np.float32(points)).reshape(-1, 1, 2)

    def reference_state_from_image(self, image):
        if image is None:
            return None

        gray = self.to_gray(image)
        kp, des = self.orb.detectAndCompute(gray, None)
        if not kp or len(kp) < self.min_reference_keypoints or des is None:
            return None

        h, w = gray.shape
        return {
            "kp": kp,
            "des": des,
            "shape": (h, w),
            "pts": self._reference_corners(h, w),
            "path": None,
        }

    def change_binary(self, background_gray, object_gray):
        """Cleaned-up map of which pixels differ between the two frames.

        Both arguments must come from :meth:`to_diff_gray`. Returns None when
        the two frames cannot be compared at all.
        """
        if background_gray is None or object_gray is None:
            return None
        if background_gray.shape != object_gray.shape:
            return None

        try:
            difference = cv2.absdiff(background_gray, object_gray)
        except cv2.error:
            return None
        _, binary = cv2.threshold(
            difference, self.object_mask_threshold, 255, cv2.THRESH_BINARY
        )
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
        return cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

    def change_profile(self, background_gray, object_gray) -> tuple[float, float]:
        """(fraction of the view that changed, share held by its largest region).

        Lets a caller say *why* :meth:`object_mask` refused without repeating
        the pipeline: a large changed fraction means the view moved, and a low
        dominance means the change is scattered rather than one thing placed in
        front of the camera.
        """
        binary = self.change_binary(background_gray, object_gray)
        if binary is None:
            return 0.0, 0.0
        frame_area = float(binary.shape[0] * binary.shape[1])
        changed = float(np.count_nonzero(binary))
        if frame_area <= 0 or changed <= 0:
            return 0.0, 0.0
        count, _, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
        if count <= 1:
            return changed / frame_area, 0.0
        largest = float(np.max(stats[1:, cv2.CC_STAT_AREA]))
        return changed / frame_area, largest / changed

    def object_mask(self, background_gray, object_gray):
        """Where the object frame differs from the scene behind it.

        Both arguments must come from :meth:`to_diff_gray`, not :meth:`to_gray`
        — see that method for what equalisation does to a difference.

        Descriptor-level subtraction was the obvious approach and is not good
        enough: hundreds of background keypoints survive with descriptors just
        different enough to look novel. Masking by pixel difference asks the
        question directly instead — which part of the frame changed when the
        object was held up — and hands that region to ORB, which takes a mask
        natively.

        Assumes the camera does not move between the two frames. That is the
        tripod setup the demo uses, and the setup whose fixed background caused
        the original defect.

        Returns None when the change is too small to be an object, or so large
        that the whole scene moved rather than something being placed in it.
        """
        binary = self.change_binary(background_gray, object_gray)
        if binary is None:
            return None

        frame_area = float(binary.shape[0] * binary.shape[1])
        if frame_area <= 0:
            return None
        changed = float(np.count_nonzero(binary))
        # Checked on the total, before picking a component. A view that changed
        # everywhere still has a largest blob, and that blob can be small enough
        # to pass for an object while describing a room that moved.
        if changed / frame_area > self.max_object_area_ratio:
            return None
        if changed <= 0:
            return None

        # connectivity is keyword-only in practice: passing 8 positionally lands
        # it in the `labels` output slot, not connectivity.
        count, labels, stats, _ = cv2.connectedComponentsWithStats(
            binary, connectivity=8
        )
        if count <= 1:
            return None
        # Largest component excluding the background label at index 0.
        largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        mask = np.where(labels == largest, 255, 0).astype(np.uint8)

        area = float(np.count_nonzero(mask))
        if area / frame_area < self.min_object_area_ratio:
            return None
        if area / changed < self.min_object_dominance:
            return None
        return mask

    def object_reference_state(self, background_image, object_image):
        """Reference template built only from the region the object occupies.

        Returns None when no usable object region is found, or when too few
        keypoints fall inside it — the honest outcome for an object that does
        not stand out from what is behind it. Callers must still run the
        capture-time negative test in :meth:`explains_frame`; this restricts
        *where* the template comes from, and that check proves it worked.

        The two greyscales are not interchangeable: the mask is found on raw
        intensity, where a difference means something moved, while the
        descriptors are cut from the equalised image so they sit in the same
        space as the live frames they are later matched against.
        """
        if background_image is None or object_image is None:
            return None

        mask = self.object_mask(
            self.to_diff_gray(background_image), self.to_diff_gray(object_image)
        )
        if mask is None:
            return None

        object_gray = self.to_gray(object_image)
        kp, des = self.orb.detectAndCompute(object_gray, mask)
        if not kp or len(kp) < self.min_reference_keypoints or des is None:
            return None

        h, w = object_gray.shape
        return {
            "kp": kp,
            "des": des,
            "shape": (h, w),
            "pts": self._reference_corners(h, w),
            "path": None,
        }

    def effective_thresholds(self, ref_state) -> tuple[int, int]:
        """(good matches, inliers) required of *ref_state*, given its size.

        Scaled to the template's own keypoint count, floored so a tiny template
        still has to agree on something, and capped at the absolute counts so
        this can only ever relax the check, never tighten it.
        """
        kp = None if ref_state is None else ref_state.get("kp")
        count = 0 if kp is None else len(kp)
        good = min(
            self.min_good_matches,
            max(self.GOOD_MATCH_FLOOR, round(self.min_good_match_ratio * count)),
        )
        inliers = min(
            self.min_inliers,
            max(self.INLIER_FLOOR, round(self.min_inlier_ratio * count)),
        )
        return int(good), int(inliers)

    def explains_frame(self, ref_state, frame_gray) -> bool:
        """Whether *ref_state* still matches a frame it must not match.

        Used as the capture-time negative test: a template that answers to the
        background is refused rather than stored, so the defect cannot ship
        silently the way it did before.
        """
        return self.match_reference_state(ref_state, frame_gray) is not None

    def reference_state_from_arrays(self, des, kp_data, shape):
        kp = [
            cv2.KeyPoint(
                x=float(row[0]),
                y=float(row[1]),
                size=float(row[2]),
                angle=float(row[3]),
                response=float(row[4]),
                octave=int(row[5]),
                class_id=int(row[6]),
            )
            for row in kp_data
        ]
        if not kp or des is None or len(kp) < self.min_reference_keypoints:
            return self.empty_reference()

        shape = tuple(int(v) for v in shape)
        h, w = shape
        return {
            "kp": kp,
            "des": des,
            "shape": shape,
            "pts": self._reference_corners(h, w),
            "path": None,
        }

    def match_reference_state(self, ref_state, frame_gray):
        ref_des = ref_state["des"]
        ref_kp = ref_state["kp"]
        ref_pts = ref_state["pts"]
        if ref_des is None or ref_kp is None or ref_pts is None or frame_gray is None:
            return None

        kp, des = self.orb.detectAndCompute(frame_gray, None)
        if des is None or len(des) <= self.min_frame_descriptors:
            return None

        return self.match_descriptors(ref_state, kp, des)

    def match_descriptors(self, ref_state, kp, des):
        ref_des = ref_state["des"]
        ref_kp = ref_state["kp"]
        if ref_des is None or ref_kp is None or des is None or kp is None:
            return None

        required_good, required_inliers = self.effective_thresholds(ref_state)

        matches = self.bf.knnMatch(ref_des, des, k=2)
        good_matches = []
        for pair in matches:
            if len(pair) < 2:
                continue
            m, n = pair
            if m.distance < self.lowe_ratio * n.distance:
                good_matches.append(m)

        if len(good_matches) <= required_good:
            return None

        src_points: Any = [ref_kp[m.queryIdx].pt for m in good_matches]
        src_pts = cast(Any, np.float32(src_points)).reshape(-1, 1, 2)
        dst_points: Any = [kp[m.trainIdx].pt for m in good_matches]
        dst_pts = cast(Any, np.float32(dst_points)).reshape(-1, 1, 2)
        homography, mask = cv2.findHomography(
            src_pts, dst_pts, cv2.RANSAC, self.ransac_reprojection
        )
        if homography is None or mask is None:
            return None

        inliers = int(mask.ravel().tolist().count(1))
        if inliers <= required_inliers:
            return None

        return {
            "homography": homography,
            "inliers": inliers,
            "good_matches": len(good_matches),
            "required_inliers": required_inliers,
            "required_good_matches": required_good,
        }

    def score_frame(self, ref_state, frame_gray):
        """What *frame_gray* scores against *ref_state*, cutoffs not applied.

        `match_reference_state` answers None for everything below threshold,
        which collapses "scored 17, needed 19" and "scored nothing at all" into
        one answer. Those ask for opposite things - the first wants the object
        moved a little, the second wants a different object - and a person
        holding the object up cannot tell them apart from a badge that only
        says no.

        Returns keypoint count, good matches, inliers and the two bars, or None
        when there is nothing to score against.
        """
        if frame_gray is None:
            return None
        kp, des = self.orb.detectAndCompute(frame_gray, None)
        return self.score_descriptors(ref_state, kp, des)

    def score_descriptors(self, ref_state, kp, des):
        """`score_frame` against descriptors already extracted from the frame.

        Separate so a caller scoring several templates against one frame pays
        for feature extraction once, which is most of the cost on this
        hardware.
        """
        ref_des = ref_state.get("des")
        ref_kp = ref_state.get("kp")
        if ref_des is None or ref_kp is None:
            return None

        required_good, required_inliers = self.effective_thresholds(ref_state)
        base = {
            "keypoints": len(ref_kp),
            # How much texture the camera is finding *right now*, which decides
            # whether a low score means "wrong object" or "the camera is seeing
            # a blur". Without it the two are indistinguishable: a template of
            # 213 keypoints scoring 5 reads the same whether the frame offered
            # 900 candidates or 6.
            "frame_keypoints": 0,
            "good_matches": 0,
            "inliers": 0,
            "required_good_matches": required_good,
            "required_inliers": required_inliers,
        }
        if des is None or kp is None:
            return base
        base["frame_keypoints"] = len(kp)

        good_matches = []
        for pair in self.bf.knnMatch(ref_des, des, k=2):
            if len(pair) < 2:
                continue
            m, n = pair
            if m.distance < self.lowe_ratio * n.distance:
                good_matches.append(m)
        base["good_matches"] = len(good_matches)

        # findHomography needs four correspondences before it can fit anything.
        if len(good_matches) < 4:
            return base

        src_points: Any = [ref_kp[m.queryIdx].pt for m in good_matches]
        src_pts = cast(Any, np.float32(src_points)).reshape(-1, 1, 2)
        dst_points: Any = [kp[m.trainIdx].pt for m in good_matches]
        dst_pts = cast(Any, np.float32(dst_points)).reshape(-1, 1, 2)
        _homography, mask = cv2.findHomography(
            src_pts, dst_pts, cv2.RANSAC, self.ransac_reprojection
        )
        if mask is not None:
            base["inliers"] = int(mask.ravel().tolist().count(1))
        return base
