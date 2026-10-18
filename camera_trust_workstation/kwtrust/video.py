"""Optional offline OpenCV numerical observation of original mounted AVI files.

Never exports pixels or media and NEVER labels a camera physically healthy.
Only processes selected bounded Phase3R/S windows with SHA-256 pinned source.
"""
from __future__ import annotations
import hashlib
import math
from pathlib import Path
from typing import Any

from .analysis import EvidenceError, require

VIDEO_STATUS = "UNVERIFIED_LOCAL_VIDEO_FEATURES_NOT_GROUND_TRUTH"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for buf in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(buf)
    return h.hexdigest()


def read_frame(cap: Any, cv2: Any, number: int):
    require(number >= 1, "1-based source frame expected")
    if not cap.set(cv2.CAP_PROP_POS_FRAMES, number - 1):
        raise EvidenceError("Decoder cannot seek to target frame")
    ok, frame = cap.read()
    if not ok or frame is None:
        raise EvidenceError(f"Could not decode source frame {number}")
    position = float(cap.get(cv2.CAP_PROP_POS_FRAMES))
    if not math.isfinite(position) or abs(position - number) > 0.51:
        raise EvidenceError(f"Source decoder-position mismatch: requested {number}, read {position}")
    return frame


def numeric_features(frame: Any, cv2: Any) -> dict:
    # Privacy: scalar statistics only. RGB, gray, and ORB arrays stay in RAM.
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    mean, std = cv2.meanStdDev(gray)
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    return {
        "mean_luma": float(mean[0][0]),
        "luma_std": float(std[0][0]),
        "laplacian_variance": float(lap.var()),
    }




def _geometric_proxy(first_gray: Any, current_gray: Any, cv2: Any):
    """Purely exploratory ORB/homography proxy, no camera-motion assertion.

    Failure to find stable correspondences remains UNKNOWN, NOT still/healthy.
    Dynamic subjects, lighting, occlusion, and parallax can confound matches.
    """
    # Resize to cap spatial compute; all arrays remain in memory.
    height, width = first_gray.shape
    scale = min(1.0, 640 / max(height, width))
    if scale < 1:
        new_size = (max(1, round(width*scale)), max(1, round(height*scale)))
        first_gray = cv2.resize(first_gray, new_size)
        current_gray = cv2.resize(current_gray, new_size)
    orb = cv2.ORB_create(nfeatures=400)
    kp_a, desc_a = orb.detectAndCompute(first_gray, None)
    kp_b, desc_b = orb.detectAndCompute(current_gray, None)
    if desc_a is None or desc_b is None or len(kp_a) < 10 or len(kp_b) < 10:
        return None
    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
    good = []
    for pair in matcher.knnMatch(desc_a, desc_b, k=2):
        if len(pair) == 2 and pair[0].distance < .75 * pair[1].distance:
            good.append(pair[0])
    if len(good) < 10:
        return None
    import numpy as np
    a = np.float32([kp_a[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    b = np.float32([kp_b[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    try:
        matrix, inliers = cv2.findHomography(a, b, cv2.RANSAC, 4.0)
        if matrix is None or inliers is None or int(inliers.sum()) < 8:
            return None
        h, w = first_gray.shape
        center = np.float32([[[w*.5,h*.5]]])
        moved = cv2.perspectiveTransform(center, matrix)[0][0]
        distance = float(np.linalg.norm(moved - center[0][0]))
        if not math.isfinite(distance):
            return None
        return {
            "good_feature_correspondences": len(good),
            "ransac_inliers": int(inliers.sum()),
            "normalized_center_displacement_proxy": round(
                distance / math.hypot(h, w), 6
            ),
        }
    except (cv2.error, ValueError, FloatingPointError):
        return None


def analyze_case(cap: Any, cv2: Any, win: dict,
                 *, max_positions: int = 12) -> dict:
    require(type(max_positions) is int and 4 <= max_positions <= 48,
            "Bounded 4..48 sample positions required")
    start, end = win["start_frame"], win["end_frame"]
    # Fixed endpoints plus evenly spaced *causal* sample positions.
    count = min(max_positions, end-start+1)
    positions = sorted(set(start + round(i*(end-start)/(count-1))
                           for i in range(count)))
    numbers = []
    geometric = []
    first_gray = None
    for n in positions:
        frame = read_frame(cap, cv2, n)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if first_gray is None:
            first_gray = gray
        else:
            geometric.append(_geometric_proxy(first_gray, gray, cv2))
        features = numeric_features(frame, cv2)
        features["sample_frame"] = n
        numbers.append(features)
    first, last = numbers[0], numbers[-1]
    initial = max(first["laplacian_variance"], 1e-9)
    sharpness_ratios = [x["laplacian_variance"]/initial for x in numbers]
    luma = [x["mean_luma"] for x in numbers]
    luma_jumps = [abs(b-a) for a,b in zip(luma,luma[1:])]
    worst = min(sharpness_ratios)
    # Proxy thresholds are descriptive diagnostics ONLY, never a decision
    # threshold or new operational warning policy.
    return {
        "status": VIDEO_STATUS,
        "sampled_source_frames": len(positions),
        "first_sample_frame": first["sample_frame"],
        "last_sample_frame": last["sample_frame"],
        "first_frame_laplacian_variance": round(first["laplacian_variance"], 5),
        "last_frame_laplacian_variance": round(last["laplacian_variance"], 5),
        "min_laplacian_ratio_to_first_window_frame": round(worst, 5),
        "max_luma_delta_between_sparse_samples": round(max(luma_jumps, default=0), 4),
        "mean_luma_range": round(max(luma)-min(luma), 4),
        "geometric_proxy_supported_comparisons": sum(x is not None for x in geometric),
        "geometric_proxy_unknown_comparisons": sum(x is None for x in geometric),
        "max_normalized_center_displacement_proxy": (
            max(x["normalized_center_displacement_proxy"]
                for x in geometric if x is not None)
            if any(x is not None for x in geometric) else None
        ),
        "scene_geometry_proxy_not_camera_displacement_truth": True,
        "derived_sparse_feature_assessment": (
            "SUBSTANTIAL_SPARSE_SHARPNESS_CHANGE_POSSIBLE" if worst < .5 else
            "NO_LARGE_SPARSE_SHARPNESS_CHANGE_OBSERVED"
        ),
        "feature_cutoff_not_production_approved": True,
        "approved_camera_reference_used": False,
        "independent_video_ground_truth": False,
        "camera_tamper_event_proven": False,
        "physical_camera_health_verified": False,
        "has_independent_visual_truth": False,
        "scene_incident_or_recovery_changed": False,
        "video_or_frames_exported": False,
    }


def analyze_videos(parsed: dict, day_paths: dict,
                   *, max_cases_per_day: int = 10,
                   samples_per_case: int = 12) -> dict:
    try:
        import cv2
    except ImportError as exc:
        raise EvidenceError("Install opencv-python-headless to inspect mounted local video") from exc
    require(type(max_cases_per_day) is int and 1 <= max_cases_per_day <= 20,
            "Limit video processing to 1..20 bounded windows/day")
    results = {}
    for day in ("day3", "day4"):
        source = Path(day_paths[day]).resolve()
        require(source.is_file(), f"Video file missing for {day}: {source}")
        require(source.suffix.lower() == ".avi", "Only source AVI video permitted")
        expected = parsed["source_pins"][day]["video_sha256"]
        actual = sha256_file(source)
        require(actual == expected,
                f"Video SHA-256 differs from pinned research recording: {day}")
        windows = [w for w in parsed["windows"] if w["day"] == day]
        # Prioritize already-observed persistent numerical candidate windows;
        # preserve selected negative comparator windows if slots remain.
        windows.sort(key=lambda w: (-w["policies"]["sharpness_3_consecutive"]["episodes"],
                                    w["start_frame"]))
        selection = windows[:max_cases_per_day]
        cap = cv2.VideoCapture(str(source))
        require(cap.isOpened(), f"Cannot open AVI decoder for {day}")
        try:
            fps = float(cap.get(cv2.CAP_PROP_FPS))
            frame_count = float(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            require(math.isfinite(fps) and fps > 0 and
                    math.isfinite(frame_count) and frame_count >= max(
                        w["end_frame"] for w in selection),
                    f"Video decoder metadata cannot support {day} frame intervals")
            for win in selection:
                results[win["id"]] = analyze_case(cap, cv2, win,
                                                  max_positions=samples_per_case)
        finally:
            cap.release()
    return results
