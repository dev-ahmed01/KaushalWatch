#!/usr/bin/env python3
"""Forensic movement-gate diagnostics on UHCTD development video.

Replays the same four movement selections as survey_uhctd_events.py and
the numbered healthy-control window implicated in false alarms.
Keeps the actual detector unchanged; all additional scene references
are diagnostic counterfactuals only, never enrolled as trusted references.

Examples:
  python scripts/diagnose_uhctd_movement.py \
    --video C:/Users/Admin/Desktop/MEVA/video.avi \
    --annotations C:/Users/Admin/Desktop/MEVA/annotations-1.csv \
    --out C:/Users/Admin/Desktop/MEVA/phase7_movement_diagnostics
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from app.services.camera_trust import (  # noqa: E402
    CameraTrustState, _scene_correlation, assess_camera, blur_score, luminance
)
from survey_uhctd_events import (  # noqa: E402
    annotation_intervals, current_revision, file_hash, select_spans
)


def registration_metrics(reference: np.ndarray, frame: np.ndarray) -> dict:
    """Reproduce v3 phase-correlation registration without gating it."""
    def edges(image: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        small = cv2.resize(gray, (192, 144))
        return cv2.Laplacian(cv2.equalizeHist(small), cv2.CV_32F)

    first = edges(reference)
    second = edges(frame)
    texture_ok = float(np.std(first)) >= 5.0 and float(np.std(second)) >= 5.0
    if not texture_ok:
        return {"response": 0.0, "offset_pixels": 0.0,
                "dx": 0.0, "dy": 0.0, "geometry_pass": False,
                "reference_texture_ok": False}
    (dx, dy), response = cv2.phaseCorrelate(first, second)
    if not np.isfinite([dx, dy, response]).all():
        return {"response": 0.0, "offset_pixels": 0.0,
                "dx": 0.0, "dy": 0.0, "geometry_pass": False,
                "reference_texture_ok": True}
    shift = float(np.hypot(dx, dy))
    return {
        "response": round(float(response), 5),
        "offset_pixels": round(shift, 3),
        "dx": round(float(dx), 3),
        "dy": round(float(dy), 3),
        "geometry_pass": bool(response >= 0.25 and shift >= 3.5),
        "reference_texture_ok": True,
    }


def gate_metrics(reference: np.ndarray, current: np.ndarray,
                 previous: np.ndarray | None) -> dict:
    """Forensic logging of the existing movement gates, not a new decision."""
    corr = _scene_correlation(reference, current)
    blur_ratio = blur_score(current) / max(0.001, blur_score(reference))
    light_delta = abs(luminance(current) - luminance(reference))
    neighbor_corr = _scene_correlation(previous, current) if previous is not None else 0.
    obstruction_eligible = (
        corr < 0.66 and (blur_ratio < 0.12 or blur_ratio > 7.0)
        and luminance(current) >= 28.0
        and not (
            luminance(current) >= 28.0
            and luminance(current) <= 0.75 * luminance(reference)
            and blur_ratio < 0.15
        )
    )
    checks = {
        "scene_corr": bool(corr < 0.66),
        "texture_ratio": bool(0.35 <= blur_ratio <= 5.0),
        "light_delta": bool(light_delta <= 50.0),
        "neighbor_corr": bool(previous is not None and neighbor_corr > 0.72),
        "not_global_obstruction": not obstruction_eligible,
    }
    geometric = registration_metrics(reference, current)
    return {
        "corr": round(float(corr), 5),
        "blur_ratio": round(float(blur_ratio), 5),
        "light_delta": round(float(light_delta), 3),
        "neighbor_corr": round(float(neighbor_corr), 5),
        **{f"gate_{key}": val for key, val in checks.items()},
        **geometric,
        "all_legacy_gates": bool(all(checks.values())),
        "ungated_geometric_shift": geometric["geometry_pass"],
    }


def inspect_span(cap, original: np.ndarray, span: dict, fps: float,
                 step: int, writer: csv.DictWriter):
    offset = span["start"] - 1
    if not cap.set(cv2.CAP_PROP_POS_FRAMES, offset):
        raise ValueError(f"Decoder refused seek to {offset}")
    position = cap.get(cv2.CAP_PROP_POS_FRAMES)
    if abs(position - offset) > 1:
        raise ValueError(f"Imprecise decoder seek: {position}, expected {offset}")
    state = CameraTrustState(reference_frame=original.copy())
    local = None
    previous = None
    observed = Counter()
    reason_counts = Counter()
    offsets = {"original": [], "local": []}
    for frame1 in range(span["start"], span["end"] + 1):
        if (frame1 - span["start"]) % step:
            if not cap.grab():
                raise ValueError(f"Video ended while advancing to frame {frame1}")
            continue
        ok, frame = cap.read()
        if not ok:
            raise ValueError(f"Video decode failure at frame {frame1}")
        if local is None:
            local = frame.copy()
        trust = assess_camera(frame, state=state, sample_seconds=step / fps)
        positive = span["onset"] is not None and frame1 >= span["onset"]
        observed["samples"] += 1
        observed["positive_samples"] += int(positive)
        observed["tamper_alert_samples"] += int(trust.tamper_suspected)
        observed["positive_tamper_alert_samples"] += int(positive and trust.tamper_suspected)
        observed["unusable_samples"] += int(not trust.trusted)
        for reason in trust.reasons:
            reason_counts[reason] += 1
        row = {
            "span": span["name"],
            "class": span["kind"],
            "extent": span["extent"],
            "frame": frame1,
            "time_sec": round((frame1 - 1) / fps, 3),
            "after_onset": bool(positive),
            "tamper_alert": bool(trust.tamper_suspected),
            "quality_unusable": not trust.trusted,
            "reasons": "; ".join(trust.reasons),
        }
        for name, ref in (("original", original), ("local", local)):
            diagnostic = gate_metrics(ref, frame, previous)
            row.update({f"{name}_{key}": value for key, value in diagnostic.items()})
            if positive or span["kind"] == 0:
                observed[f"{name}_geometry_pass"] += int(diagnostic["geometry_pass"])
                observed[f"{name}_legacy_gate_pass"] += int(diagnostic["all_legacy_gates"])
                observed[f"{name}_both_pass"] += int(
                    diagnostic["geometry_pass"] and diagnostic["all_legacy_gates"]
                )
            offsets[name].append(diagnostic["offset_pixels"])
        writer.writerow(row)
        previous = frame
    result = {**span, **dict(observed), "reason_samples": dict(reason_counts)}
    for name in offsets:
        result[f"{name}_median_registration_offset"] = round(
            float(np.median(offsets[name])), 3
        ) if offsets[name] else None
    return result


def diagnose(video: Path, annotations: Path, out: Path,
             *, normal_window: int = 8, events_per_class: int = 4,
             normal_windows: int = 12, sample_seconds: float = 0.333333):
    if not math.isfinite(sample_seconds) or sample_seconds <= 0:
        raise ValueError("Sample period must be finite and positive")
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise ValueError(f"Cannot open {video}")
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if not math.isfinite(fps) or fps <= 0 or count < 1:
            raise ValueError("Invalid video metadata")
        runs, annotated_count = annotation_intervals(annotations)
        if annotated_count != count:
            raise ValueError(f"Video/labels differ: {count} vs {annotated_count} frames")
        spans = select_spans(runs, fps, events_per_class, normal_windows,
                             120, 20, 90)
        name = f"normal_control_{normal_window}"
        chosen = [span for span in spans if span["kind"] == 3 or span["name"] == name]
        if len(chosen) != events_per_class + 1:
            raise ValueError(f"Expected {events_per_class} moved spans plus {name}")
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        ok, first = cap.read()
        if not ok:
            raise ValueError("Cannot read initial reference frame")
        step = max(1, round(fps * sample_seconds))
        out.mkdir(parents=True, exist_ok=True)
        raw = out / "movement_gate_samples.csv"
        names = ["span", "class", "extent", "frame", "time_sec", "after_onset",
                 "tamper_alert", "quality_unusable", "reasons"]
        gate_names = list(gate_metrics(first, first, None))
        names += [f"{ref}_{key}" for ref in ("original", "local")
                  for key in gate_names]
        findings = []
        with raw.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=names)
            writer.writeheader()
            for i, span in enumerate(chosen, 1):
                result = inspect_span(cap, first, span, fps, step, writer)
                findings.append(result)
                print(
                    f"[{i}/{len(chosen)}] {span['name']} suspect="
                    f"{result.get('tamper_alert_samples',0)}/{result.get('samples',0)} "
                    f"geometry_original={result.get('original_geometry_pass',0)} "
                    f"geometry_local={result.get('local_geometry_pass',0)}",
                    flush=True,
                )
        summary = {
            "evaluation_status": "DEVELOPMENT_MOVEMENT_FORENSICS_NOT_VALIDATION",
            "model_commit": current_revision(),
            "annotations_sha256": file_hash(annotations),
            "video": str(video.resolve()),
            "fps": fps,
            "sample_period_seconds": step/fps,
            "spans": findings,
            "limitations": [
                "Only four selected moved events and one flagged normal window.",
                "Local pre-onset reference is diagnostic; it must not be silently enrolled.",
                "Span state resets; results are not continuous 24-hour operational scores.",
                "Survey fourth moved event extent parameter equals 0; verify visual motion.",
                "Some stationary foreground objects can imitate displacement.",
                "The script does not export video frames.",
            ],
        }
        (out / "movement_gate_summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
        return summary
    finally:
        cap.release()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--video", required=True, type=Path)
    p.add_argument("--annotations", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--normal-window", type=int, default=8)
    p.add_argument("--sample-seconds", type=float, default=0.333333)
    args = p.parse_args()
    result = diagnose(args.video, args.annotations, args.out,
                      normal_window=args.normal_window,
                      sample_seconds=args.sample_seconds)
    print(json.dumps({
        "status": result["evaluation_status"],
        "results": result["spans"],
        "output": str(args.out.resolve()),
    }, indent=2))


if __name__ == "__main__":
    main()
