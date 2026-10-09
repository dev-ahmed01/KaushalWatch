#!/usr/bin/env python3
"""Inspect UHCTD healthy-video obstruction alarms without changing detector thresholds.

Only samples representative *annotated normal* windows, not a full 24-hour
replay or held-out validation. Compares the original first-frame reference
against a window-local healthy reference. Writes numerical features only;
NEVER saves images, crops, or dataset video.

Run from the repository root or elsewhere:
  python scripts/diagnose_uhctd_obstruction.py \
    --video "C:/Users/Admin/Desktop/MEVA/UHCTD_Day4/video.avi" \
    --annotations "C:/Users/Admin/Desktop/MEVA/UHCTD_Day4/annotations.csv" \
    --out "C:/Users/Admin/Desktop/MEVA/UHCTD_Day4/obstruction_probe"
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.camera_trust import (  # noqa: E402
    CameraTrustState,
    _scene_correlation,
    assess_camera,
    blur_score,
    luminance,
)


def annotation_runs(path: Path) -> tuple[list[tuple[int, int, int]], int]:
    """Contiguous runs of 1-based frame/class labels; detect gaps and mismatch."""
    runs: list[tuple[int, int, int]] = []
    previous_class = None
    first = 1
    count = 0
    with path.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.reader(source):
            if not row or not any(value.strip() for value in row):
                continue
            if len(row) < 2:
                raise ValueError(f"Bad annotation CSV at row {count + 1}")
            frame_no, cls = int(row[0]), int(row[1])
            if frame_no != count + 1 or cls not in (0, 1, 2, 3):
                raise ValueError(f"Unexpected annotation frame/class: {frame_no}, {cls}")
            if previous_class is not None and cls != previous_class:
                runs.append((previous_class, first, count))
                first = frame_no
            previous_class = cls
            count += 1
    if previous_class is None:
        raise ValueError("Empty annotations CSV")
    runs.append((previous_class, first, count))
    return runs, count


def choose_normal_windows(
    runs: list[tuple[int, int, int]],
    total_frames: int,
    fps: float,
    n_windows: int,
    duration_seconds: float,
    margin_seconds: float,
) -> list[dict]:
    if n_windows < 1 or duration_seconds <= 0 or margin_seconds < 0:
        raise ValueError("Invalid window count, duration or margin")
    width = math.ceil(duration_seconds * fps)
    margin = math.ceil(margin_seconds * fps)
    usable = [
        (low, high)
        for cls, low, high in runs
        if cls == 0 and high - low + 1 >= width + 2 * margin
    ]
    if not usable:
        raise ValueError("No normal segments long enough for requested windows")
    if len(usable) < n_windows:
        raise ValueError(
            f"Only {len(usable)} nonoverlapping normal segments available "
            f"for {n_windows} requested windows; reduce --windows"
        )
    chosen = []
    remaining = usable.copy()
    for i in range(n_windows):
        target = (i + 0.5) * total_frames / n_windows
        segment = min(remaining, key=lambda bounds: (
            abs((bounds[0] + bounds[1]) / 2 - target), bounds[0]
        ))
        remaining.remove(segment)
        low, high = segment
        low_start = low + margin
        high_start = high - margin - width + 1
        start = max(low_start, min(high_start, round(target - width / 2)))
        chosen.append({
            "window": i + 1,
            "segment_start_frame": low,
            "segment_end_frame": high,
            "start_frame": start,
            "end_frame": start + width - 1,
        })
    return sorted(chosen, key=lambda item: item["start_frame"])


def _features(reference, frame) -> dict:
    sharpness = blur_score(frame)
    reference_sharpness = max(0.001, blur_score(reference))
    contrast_ratio = sharpness / reference_sharpness
    mean_light = luminance(frame)
    ref_light = luminance(reference)
    correlation = _scene_correlation(reference, frame)
    # This mirrors the detector rule at the v3 candidate commit.
    raw_candidate = (
        correlation < 0.66
        and (contrast_ratio < 0.12 or contrast_ratio > 7.0)
        and mean_light >= 28.0
    )
    return {
        "reference_correlation": round(correlation, 5),
        "blur_ratio": round(contrast_ratio, 5),
        "blur_score": round(sharpness, 4),
        "luminance": round(mean_light, 3),
        "reference_luminance": round(ref_light, 3),
        "luminance_delta": round(abs(mean_light - ref_light), 3),
        "raw_obstruction_candidate": bool(raw_candidate),
        "blur_ratio_low": bool(contrast_ratio < 0.12),
        "blur_ratio_high": bool(contrast_ratio > 7.0),
    }


def _git_sha() -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=False,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except OSError:
        return None


def diagnose(
    video: Path,
    annotations: Path,
    out: Path,
    *,
    windows: int = 12,
    duration_seconds: float = 90.0,
    margin_seconds: float = 20.0,
    sample_seconds: float = 0.2,
) -> dict:
    if not math.isfinite(sample_seconds) or sample_seconds <= 0:
        raise ValueError("--sample-seconds must be positive")
    if not video.is_file() or not annotations.is_file():
        raise ValueError("Video and annotation CSV must exist")
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise ValueError(f"Could not open {video}")
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if not math.isfinite(fps) or fps <= 0 or n_frames < 1:
            raise ValueError("Cannot determine video FPS and frame count")
        runs, annotation_count = annotation_runs(annotations)
        if annotation_count != n_frames:
            raise ValueError(
                f"Video/annotation mismatch: {n_frames} vs {annotation_count} frames"
            )
        selections = choose_normal_windows(
            runs, n_frames, fps, windows, duration_seconds, margin_seconds
        )
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        success, original_reference = cap.read()
        if not success:
            raise ValueError("Unable to decode original frame 1")
        step = max(1, round(sample_seconds * fps))
        actual_interval = step / fps

        out.mkdir(parents=True, exist_ok=True)
        samples_file = out / "obstruction_samples.csv"
        fields = [
            "window", "frame", "second", "mode", "trusted",
            "tamper_suspected", "reason_obstructed", "reasons",
            "reference_correlation", "blur_ratio", "blur_score",
            "luminance", "reference_luminance", "luminance_delta",
            "raw_obstruction_candidate", "blur_ratio_low", "blur_ratio_high",
        ]
        per_window = []
        totals = {
            mode: Counter() for mode in ("initial_reference", "local_reference")
        }
        with samples_file.open("w", encoding="utf-8", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=fields)
            writer.writeheader()
            for window in selections:
                first0 = window["start_frame"] - 1
                if not cap.set(cv2.CAP_PROP_POS_FRAMES, first0):
                    raise ValueError(f"Seek failed to frame {first0}")
                observed_seek = cap.get(cv2.CAP_PROP_POS_FRAMES)
                if abs(observed_seek - first0) > 1:
                    raise ValueError(
                        f"Imprecise decoder seek: expected {first0}, got {observed_seek}"
                    )
                success, local_reference = cap.read()
                if not success:
                    raise ValueError(f"Could not read window {window['window']}")
                states = {
                    "initial_reference": CameraTrustState(),
                    "local_reference": CameraTrustState(),
                }
                counters = {key: Counter() for key in states}
                sampled = 0
                last0 = window["end_frame"] - 1
                for index0 in range(first0, last0 + 1):
                    if index0 == first0:
                        frame = local_reference
                    elif index0 % step == first0 % step:
                        ok, frame = cap.read()
                        if not ok:
                            raise ValueError(f"Unexpected EOF at frame {index0+1}")
                    else:
                        if not cap.grab():
                            raise ValueError(f"Could not advance to frame {index0+1}")
                        continue
                    sampled += 1
                    for mode, reference in (
                        ("initial_reference", original_reference),
                        ("local_reference", local_reference),
                    ):
                        metrics = _features(reference, frame)
                        trust = assess_camera(
                            frame,
                            reference_frame=reference,
                            state=states[mode],
                            sample_seconds=actual_interval,
                        )
                        is_obstruction = (
                            "camera view may be obstructed" in trust.reasons
                        )
                        record = {
                            "window": window["window"],
                            "frame": index0 + 1,
                            "second": round(index0 / fps, 3),
                            "mode": mode,
                            "trusted": trust.trusted,
                            "tamper_suspected": trust.tamper_suspected,
                            "reason_obstructed": is_obstruction,
                            "reasons": "; ".join(trust.reasons),
                            **metrics,
                        }
                        writer.writerow(record)
                        c = counters[mode]
                        c["samples"] += 1
                        c["untrusted"] += int(not trust.trusted)
                        c["tamper_suspected"] += int(trust.tamper_suspected)
                        c["obstructed"] += int(is_obstruction)
                        c["raw_obstruction_candidate"] += int(
                            metrics["raw_obstruction_candidate"]
                        )
                        c["low_texture"] += int(metrics["blur_ratio_low"])
                        c["high_texture"] += int(metrics["blur_ratio_high"])
                window_result = {
                    **window,
                    "start_seconds": round(first0 / fps, 3),
                    "end_seconds": round(last0 / fps, 3),
                    "sampled_frames": sampled,
                }
                for mode in states:
                    c = counters[mode]
                    totals[mode].update(c)
                    for key in ("untrusted", "tamper_suspected", "obstructed",
                                "raw_obstruction_candidate",
                                "low_texture", "high_texture"):
                        window_result[f"{mode}_{key}"] = c[key]
                    window_result[f"{mode}_obstruction_fraction"] = round(
                        c["obstructed"] / max(1, c["samples"]), 5
                    )
                per_window.append(window_result)
                print(
                    f"Window {window['window']}/{len(selections)} "
                    f"@ {first0/fps/3600:.2f}h: "
                    f"obstructed initial {counters['initial_reference']['obstructed']}/{sampled}; "
                    f"local {counters['local_reference']['obstructed']}/{sampled}",
                    flush=True,
                )
        windows_file = out / "obstruction_windows.csv"
        with windows_file.open("w", encoding="utf-8", newline="") as file:
            fields_window = list(per_window[0])
            writer = csv.DictWriter(file, fieldnames=fields_window)
            writer.writeheader()
            writer.writerows(per_window)

        def summarize(mode):
            c = totals[mode]
            return {
                **dict(c),
                "samples": c["samples"],
                "obstructed_fraction": round(
                    c["obstructed"] / max(1, c["samples"]), 6
                ),
                "tamper_suspected_fraction": round(
                    c["tamper_suspected"] / max(1, c["samples"]), 6
                ),
                "untrusted_fraction": round(
                    c["untrusted"] / max(1, c["samples"]), 6
                ),
            }
        initial = summarize("initial_reference")
        local = summarize("local_reference")
        result = {
            "kind": "TARGETED_NORMAL_WINDOW_DIAGNOSTICS_NOT_HELD_OUT_VALIDATION",
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "git_commit": _git_sha(),
            "video": str(video.resolve()),
            "annotations": str(annotations.resolve()),
            "fps": fps,
            "video_frames": n_frames,
            "sample_step_frames": step,
            "sample_seconds": actual_interval,
            "selected_normal_windows": len(per_window),
            "total_sampled_frames_per_mode": initial["samples"],
            "initial_reference": initial,
            "local_reference": local,
            "paired_obstruction_fraction_difference": round(
                initial["obstructed_fraction"] - local["obstructed_fraction"], 6
            ),
            "limitations": [
                "Targeted normal windows only; results cannot estimate full-day recall/false alarm rate.",
                "State resets at each window; initial-reference mode does NOT reconstruct continuous state from 24h.",
                "Window-local reference is a diagnostic counterfactual, NOT a safe automatic production baseline.",
                "Neither mode authenticates stream freshness or proves intentional tampering.",
                "No video frames are exported.",
            ],
            "files": {
                "windows": str(windows_file),
                "samples": str(samples_file),
            },
        }
        (out / "obstruction_diagnostics_summary.json").write_text(
            json.dumps(result, indent=2), encoding="utf-8"
        )
        return result
    finally:
        cap.release()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--video", type=Path, required=True)
    p.add_argument("--annotations", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--windows", type=int, default=12)
    p.add_argument("--duration-seconds", type=float, default=90.0)
    p.add_argument("--margin-seconds", type=float, default=20.0)
    p.add_argument("--sample-seconds", type=float, default=0.2)
    args = p.parse_args()
    summary = diagnose(
        args.video, args.annotations, args.out, windows=args.windows,
        duration_seconds=args.duration_seconds,
        margin_seconds=args.margin_seconds,
        sample_seconds=args.sample_seconds,
    )
    print(json.dumps({
        "status": summary["kind"],
        "windows": summary["selected_normal_windows"],
        "initial_reference": summary["initial_reference"],
        "local_reference": summary["local_reference"],
        "paired_obstruction_fraction_difference":
            summary["paired_obstruction_fraction_difference"],
        "output": str(args.out.resolve()),
    }, indent=2))


if __name__ == "__main__":
    main()
