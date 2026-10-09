#!/usr/bin/env python3
"""Shadow evaluation of sustained scene-change review cues on UHCTD Day 3.

Use *only* for development footage and selected intervals. This probe DOES
NOT change the live Camera Trust decision. Its first 10 seconds are an
independently annotated healthy inspection window, not an approved
operational reference. Day 3 is not untouched held-out validation.

Example:
  python scripts/diagnose_uhctd_persistent_change.py \
    --video "C:/Users/Admin/Desktop/MEVA/video.avi" \
    --annotations "C:/Users/Admin/Desktop/MEVA/annotations-1.csv" \
    --out "C:/Users/Admin/Desktop/MEVA/phase10_change_points"
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

from app.services.camera_persistent_scene_probe import PersistentSceneProbe  # noqa: E402
from app.services.camera_trust import CameraTrustState, assess_camera  # noqa: E402
from survey_uhctd_events import (  # noqa: E402
    annotation_intervals, current_revision, file_hash, select_spans
)


FIELDS = [
    "span", "label", "extent", "frame", "time_seconds", "post_onset",
    "scene_correlation", "low_similarity", "changed_seconds",
    "persistent_review", "signal", "quality_limited",
    "production_tamper_suspected", "production_unusable",
]


def evaluate_span(cap, reference, span, fps, step, writer):
    first0 = span["start"] - 1
    if not cap.set(cv2.CAP_PROP_POS_FRAMES, first0):
        raise ValueError(f"Seek failed at {first0}")
    if abs(cap.get(cv2.CAP_PROP_POS_FRAMES) - first0) > 1:
        raise ValueError(f"Inaccurate decoder seek at {first0}")
    probe = PersistentSceneProbe()
    current = CameraTrustState(reference_frame=reference.copy())
    counts = Counter()
    first_candidate = None
    first_pre_event = None
    for frame1 in range(span["start"], span["end"] + 1):
        if (frame1 - span["start"]) % step:
            if not cap.grab():
                raise ValueError(f"Unexpected video EOF at {frame1}")
            continue
        ok, frame = cap.read()
        if not ok:
            raise ValueError(f"Could not decode sampled frame {frame1}")
        measure = probe.observe(frame, step / fps)
        trust = assess_camera(frame, state=current, sample_seconds=step / fps)
        positive = span["onset"] is not None and frame1 >= span["onset"]
        counts["samples"] += 1
        counts["post_onset_samples"] += int(positive)
        counts["review_samples"] += int(measure["persistent_review"])
        counts["low_detail_samples"] += int(measure["quality_limited"])
        counts["production_tamper_samples"] += int(trust.tamper_suspected)
        if positive:
            counts["positive_review_samples"] += int(measure["persistent_review"])
        elif measure["persistent_review"] and first_pre_event is None:
            first_pre_event = frame1
        if positive and measure["persistent_review"] and first_candidate is None:
            first_candidate = frame1
        writer.writerow({
            "span": span["name"], "label": span["kind"],
            "extent": span["extent"], "frame": frame1,
            "time_seconds": round((frame1 - 1) / fps, 3),
            "post_onset": positive, **measure,
            "production_tamper_suspected": bool(trust.tamper_suspected),
            "production_unusable": bool(not trust.trusted),
        })
    return {
        "span": span["name"], "kind": span["kind"],
        "annotation_extent": span["extent"], "onset": span["onset"],
        **dict(counts),
        "first_pre_onset_review_frame": first_pre_event,
        "first_post_onset_review_frame": first_candidate,
        "post_onset_delay_seconds": (
            round((first_candidate - span["onset"]) / fps, 3)
            if first_candidate is not None else None
        ),
        "warning": (
            "Scene change is not proven camera motion; "
            "visibility/large foreground changes may mimic it."
        ),
    }


def run(video, annotations, out, *,
        events_per_class=4, normal_windows=12, sample_seconds=1/3,
        normal_seconds=90.0):
    if not math.isfinite(sample_seconds) or sample_seconds <= 0:
        raise ValueError("Sample interval must be positive")
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise ValueError(f"Cannot open video {video}")
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if fps <= 0 or total <= 0:
            raise ValueError("Invalid video FPS/frame count")
        runs, annotated_count = annotation_intervals(annotations)
        if total != annotated_count:
            raise ValueError("Video and labels do not align")
        all_spans = select_spans(
            runs, fps, events_per_class, normal_windows,
            event_seconds=120, context_seconds=20,
            control_seconds=normal_seconds
        )
        spans = [s for s in all_spans if s["kind"] in (0, 3)]
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        ok, original = cap.read()
        if not ok:
            raise ValueError("Cannot decode first video reference")
        step = max(1, round(fps * sample_seconds))
        out.mkdir(parents=True, exist_ok=True)
        records = []
        csv_path = out / "persistent_change_samples.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as output:
            writer = csv.DictWriter(output, fieldnames=FIELDS)
            writer.writeheader()
            for i, span in enumerate(spans, 1):
                record = evaluate_span(cap, original, span, fps, step, writer)
                records.append(record)
                print(
                    f"[{i}/{len(spans)}] {span['name']}: "
                    f"review {record.get('review_samples', 0)}/"
                    f"{record.get('samples', 0)}; "
                    f"post-event first={record['post_onset_delay_seconds']}",
                    flush=True,
                )
        events = [r for r in records if r["kind"] == 3]
        controls = [r for r in records if r["kind"] == 0]
        summary = {
            "evaluation_status": "PHASE10_SHADOW_DEVELOPMENT_NOT_HELD_OUT",
            "model_commit": current_revision(),
            "video": str(video.resolve()),
            "annotations_sha256": file_hash(annotations),
            "fps": fps,
            "effective_sample_seconds": step / fps,
            "candidate_rule": {
                "healthy_startup_warmup_seconds": 10,
                "scene_corr_below": 0.67,
                "continuous_change_seconds": 12,
                "reference_promotion": "NEVER",
                "production_integrated": False,
            },
            "moved_events": len(events),
            "moved_events_with_new_review": sum(
                r["first_post_onset_review_frame"] is not None
                and r["first_pre_onset_review_frame"] is None
                for r in events
            ),
            "normal_controls": len(controls),
            "normal_controls_with_false_reviews": sum(
                bool(r.get("review_samples")) for r in controls
            ),
            "rows": records,
            "limitations": [
                "Only selected event segments and normal controls, not a 24h replay.",
                "The initial 20 seconds are annotation-confirmed healthy context.",
                "The model does not identify physical camera motion, only persistent change.",
                "A new scene reference is NEVER automatically approved from imagery.",
                "Day 3 settings and thresholds were chosen after inspecting its stills.",
                "Change-point warnings cannot replace evidence-quality or officer review.",
                "Images or video are not exported.",
            ],
        }
        (out / "persistent_change_summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
        return summary
    finally:
        cap.release()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--video", type=Path, required=True)
    p.add_argument("--annotations", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--sample-seconds", type=float, default=1/3)
    args = p.parse_args()
    result = run(
        args.video, args.annotations, args.out,
        sample_seconds=args.sample_seconds,
    )
    print(json.dumps({
        "status": result["evaluation_status"],
        "moved_events_with_new_review": result["moved_events_with_new_review"],
        "moved_events": result["moved_events"],
        "normal_controls_with_false_reviews": result["normal_controls_with_false_reviews"],
        "normal_controls": result["normal_controls"],
        "out": str(args.out.resolve()),
    }, indent=2))


if __name__ == "__main__":
    main()
