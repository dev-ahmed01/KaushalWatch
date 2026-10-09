#!/usr/bin/env python3
"""Phase 11: short-window spatial background diagnostics on UHCTD development.

Does not change live Camera Trust. All three regional-coverage thresholds are
SHADOW alternatives fixed in source, not promoted settings. Each event has
20 seconds of annotated pre-onset context; the temporary reference is the
median of its first 10 seconds. This depends on externally known healthy
context and is not a self-approved production camera baseline.

Outputs CSV/JSON ONLY, no CCTV images. No full 24-hour replay.
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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))
from app.services.camera_spatial_scene_shadow import (  # noqa: E402
    SpatialSceneShadow, THRESHOLDS,
)
from app.services.camera_persistent_scene_probe import PersistentSceneProbe  # noqa: E402
from survey_uhctd_events import (  # noqa: E402
    annotation_intervals, current_revision, file_hash, select_spans,
)

FIELDS = [
    "span", "kind", "extent", "frame", "post_onset",
    "camera_status", "global_scene_correlation", "global_review",
    "evidence_status", "eligible_tiles", "changed_tiles",
    "changed_fraction", "changed_quadrants",
    "median_tile_correlation", "median_baseline_tile_texture",
    "median_current_tile_texture",
    *[f"review_{int(k * 100)}" for k in THRESHOLDS],
]


def inspect(cap, span: dict, fps: float, step: int, writer: csv.DictWriter):
    frame_zero = span["start"] - 1
    if not cap.set(cv2.CAP_PROP_POS_FRAMES, frame_zero):
        raise ValueError(f"Video seek failed at frame {span['start']}")
    if abs(float(cap.get(cv2.CAP_PROP_POS_FRAMES)) - frame_zero) > 1:
        raise ValueError("Seek position mismatch")
    regional = SpatialSceneShadow()
    global_probe = PersistentSceneProbe()
    stats = Counter()
    first_rising = {f"review_{int(k * 100)}": None for k in THRESHOLDS}
    before = {f"review_{int(k * 100)}": False for k in THRESHOLDS}
    first_review_context = {f"review_{int(k * 100)}": False for k in THRESHOLDS}
    qualities = []
    for frame1 in range(span["start"], span["end"] + 1):
        if (frame1 - span["start"]) % step:
            if not cap.grab():
                raise ValueError(f"Video EOF at frame {frame1}")
            continue
        ok, frame = cap.read()
        if not ok:
            raise ValueError(f"Unable to decode frame {frame1}")
        info = regional.observe(frame, step / fps)
        global_info = global_probe.observe(frame, step / fps)
        positive = span["onset"] is not None and frame1 >= span["onset"]
        stats["samples"] += 1
        stats["positive_samples"] += int(positive)
        stats["low_tile_confidence_samples"] += int(
            info["evidence_status"] == "UNKNOWN_LOW_TEXTURE"
        )
        stats["global_alert_samples"] += int(global_info["persistent_review"])
        if positive:
            stats["positive_global_alert_samples"] += int(
                global_info["persistent_review"]
            )
        for key in before:
            flagged = bool(info[key])
            stats[key + "_samples"] += int(flagged)
            if positive:
                stats[key + "_positive_samples"] += int(flagged)
                if flagged and not before[key] and first_rising[key] is None:
                    first_rising[key] = frame1
            elif flagged:
                first_review_context[key] = True
            before[key] = flagged
        row = {
            "span": span["name"], "kind": span["kind"],
            "extent": span["extent"], "frame": frame1,
            "post_onset": positive,
            "camera_status": "SHADOW_NOT_INTEGRATED",
            "global_scene_correlation": global_info["scene_correlation"],
            "global_review": global_info["persistent_review"],
        }
        for key in FIELDS:
            if key in info:
                row[key] = info[key]
        writer.writerow(row)
    out = {
        "span": span["name"], "kind": span["kind"], "extent": span["extent"],
        "onset": span["onset"], **dict(stats)
    }
    for key, first in first_rising.items():
        out[key + "_fresh_after_onset"] = (
            first is not None and not first_review_context[key]
        )
        out[key + "_first_delay_seconds"] = (
            round((first - span["onset"]) / fps, 3)
            if first is not None and span["onset"] is not None else None
        )
        out[key + "_preexisting_alert"] = first_review_context[key]
    return out


def run(video: Path, annotations: Path, out: Path, *,
        events_per_class: int = 4, normal_windows: int = 12,
        normal_seconds: float = 90.0, sample_seconds: float = 1 / 3):
    if not math.isfinite(sample_seconds) or sample_seconds <= 0:
        raise ValueError("Sampling period must be finite and positive")
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise ValueError(f"Cannot open video {video}")
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if fps <= 0 or total <= 0:
            raise ValueError("Invalid video frame count or FPS")
        runs, count = annotation_intervals(annotations)
        if count != total:
            raise ValueError(f"Annotation count {count} does not match video {total}")
        chosen = select_spans(runs, fps, events_per_class, normal_windows,
                              event_seconds=120, context_seconds=20,
                              control_seconds=normal_seconds)
        spans = [r for r in chosen if r["kind"] in (0, 3)]
        out.mkdir(parents=True, exist_ok=True)
        step = max(1, round(fps * sample_seconds))
        csv_file = out / "spatial_shadow_samples.csv"
        results = []
        with csv_file.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=FIELDS)
            writer.writeheader()
            for i, span in enumerate(spans, 1):
                record = inspect(cap, span, fps, step, writer)
                results.append(record)
                text = " ".join(
                    f"{int(threshold*100)}%:{record.get('review_'+str(int(threshold*100))+'_samples', 0)}"
                    for threshold in THRESHOLDS
                )
                print(f"[{i}/{len(spans)}] {span['name']}: {text}", flush=True)

        comparisons = {}
        for threshold in THRESHOLDS:
            key = f"review_{int(threshold * 100)}"
            events = [row for row in results if row["kind"] == 3]
            controls = [row for row in results if row["kind"] == 0]
            comparisons[key] = {
                "fresh_moved_review_events": sum(
                    r[key + "_fresh_after_onset"] for r in events
                ),
                "moved_events_total": len(events),
                "normal_controls_with_false_review": sum(
                    r.get(key + "_samples", 0) > 0 for r in controls
                ),
                "normal_controls_total": len(controls),
                "false_normal_samples": sum(
                    r.get(key + "_samples", 0) for r in controls
                ),
                "unknown_quality_samples": sum(
                    r.get("low_tile_confidence_samples", 0) for r in results
                ),
            }
        summary = {
            "evaluation_status": "PHASE11_SPATIAL_SHADOW_DEVELOPMENT_NOT_HELD_OUT",
            "model_commit": current_revision(),
            "video": str(video.resolve()),
            "annotations_sha256": file_hash(annotations),
            "fps": fps, "sample_step": step,
            "effective_sample_seconds": step / fps,
            "fixed_diagnostic_thresholds": list(THRESHOLDS),
            "reference": "10-second median of annotated healthy event/window prefix",
            "production_integration": False,
            "comparisons": comparisons,
            "spans": results,
            "limitations": [
                "Source video was already used to develop the model.",
                "Thresholds are exploratory, not optimized or independently tested.",
                "All windows reset state and depend on annotation-confirmed normal prefixes.",
                "No reference is automatically approved or enrolled.",
                "Low-texture results may be UNKNOWN; they are not negatives.",
                "Regional structural differences also arise from large foreground objects, lighting and weather.",
                "Does not estimate full-day operational false alarms or true camera-movement recall.",
            ],
        }
        (out / "spatial_shadow_summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
        return summary
    finally:
        cap.release()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--sample-seconds", type=float, default=1 / 3)
    args = parser.parse_args()
    result = run(args.video, args.annotations, args.out,
                 sample_seconds=args.sample_seconds)
    print(json.dumps({
        "evaluation_status": result["evaluation_status"],
        "comparisons": result["comparisons"],
        "output": str(args.out.resolve()),
    }, indent=2))


if __name__ == "__main__":
    main()
