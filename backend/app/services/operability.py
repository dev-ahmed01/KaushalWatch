from __future__ import annotations
import cv2
import numpy as np


def apparent_motion_state(frames: list[np.ndarray], roi: tuple[int, int, int, int], threshold: float = 0.8) -> tuple[str, float]:
    """Visual activity proxy only; never a mechanical/electrical health diagnosis."""
    if len(frames) < 3:
        return "UNCERTAIN", 0.0
    x1, y1, x2, y2 = roi
    scores: list[float] = []
    prev = None
    for frame in frames:
        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            return "UNCERTAIN", 0.0
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        if prev is not None:
            scores.append(float(np.mean(cv2.absdiff(prev, gray))))
        prev = gray
    if not scores:
        return "UNCERTAIN", 0.0
    score = float(np.median(scores))
    return ("APPARENTLY_ACTIVE" if score >= threshold else "APPARENTLY_INACTIVE"), score


def trace_apparent_motion(
    video_path,
    roi: tuple[int, int, int, int],
    *,
    threshold: float = 0.8,
    max_frames: int = 30,
    window: tuple[float, float] | None = None,
) -> dict:
    """Sample exactly as the infrastructure workflow does and return a pixel-free trace.

    Shared by the case pipeline and isolated evaluation. This observes visible
    ROI motion only; it cannot establish equipment mechanical/electrical health.
    """
    import hashlib
    import math
    from pathlib import Path

    if not isinstance(max_frames, int) or isinstance(max_frames, bool) or max_frames < 3:
        raise ValueError("max_frames must be an integer >= 3")
    if not math.isfinite(float(threshold)) or float(threshold) < 0:
        raise ValueError("operability threshold must be finite and nonnegative")
    if len(roi) != 4 or any(type(x) is not int for x in roi):
        raise ValueError("ROI must be four integer pixel coordinates")
    cap = cv2.VideoCapture(str(Path(video_path)))
    if not cap.isOpened():
        raise ValueError(f"Cannot open operability video: {video_path}")

    frames: list[np.ndarray] = []
    samples: list[dict] = []
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 25.0)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        if fps <= 0 or not math.isfinite(fps) or frame_count <= 0:
            raise ValueError("Operability video has invalid FPS/frame count")
        x1, y1, x2, y2 = roi
        if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
            raise ValueError("Operability ROI extends outside video frame")
        duration = frame_count / fps
        analysis_window: dict[str, float | None] = {
            "start_sec": 0.0,
            "end_sec": round(duration, 3),
        }

        if window is None:
            cap.set(cv2.CAP_PROP_POS_MSEC, 0)
            step = max(1, int(fps / 2))
            index = 0
            while len(frames) < max_frames:
                ok, frame = cap.read()
                if not ok:
                    break
                if index % step == 0:
                    frames.append(frame)
                    samples.append({
                        "requested_second": round(index / fps, 6),
                        "frame_index": index,
                        "decoded_frame_sha256": hashlib.sha256(frame.tobytes()).hexdigest(),
                    })
                index += 1
        else:
            start, end = float(window[0]), float(window[1])
            if (not math.isfinite(start) or not math.isfinite(end)
                    or start < 0 or end <= start or end > duration + 1e-6):
                raise ValueError("Invalid operability stable measurement window")
            analysis_window = {"start_sec": round(start, 3), "end_sec": round(end, 3)}
            sample_count = min(max_frames, max(3, int((end - start) * 2.0) + 1))
            for index in range(sample_count):
                second = start + (end - start) * index / sample_count
                cap.set(cv2.CAP_PROP_POS_MSEC, second * 1000.0)
                ok, frame = cap.read()
                if not ok:
                    continue
                actual_index = int(round(cap.get(cv2.CAP_PROP_POS_FRAMES) - 1))
                frames.append(frame)
                samples.append({
                    "requested_second": round(second, 6),
                    "frame_index": actual_index,
                    "decoded_frame_sha256": hashlib.sha256(frame.tobytes()).hexdigest(),
                })
    finally:
        cap.release()

    state, score = apparent_motion_state(frames, roi, threshold=threshold)
    return {
        "state": state,
        "activity_score": round(score, 4),
        "method": "roi_motion_proxy",
        "frames_sampled": len(frames),
        "analysis_window": analysis_window,
        "threshold": float(threshold),
        "max_frames": max_frames,
        "roi": {"x1": roi[0], "y1": roi[1], "x2": roi[2], "y2": roi[3]},
        "frame_samples": samples,
        "interpretation": "Visual activity proxy only; not a mechanical/electrical health diagnosis.",
    }
