#!/usr/bin/env python3
"""Export small manual-review contact sheets for *existing UHCTD* movement spans.

This diagnostic intentionally generates local images; it never pushes them
to GitHub or auto-enrolls reference frames. Follow your UHCTD research
agreement and avoid sharing media outside permitted review channels.

Example:
  python scripts/export_uhctd_movement_review.py \
    --video "C:/Users/Admin/Desktop/MEVA/video.avi" \
    --annotations "C:/Users/Admin/Desktop/MEVA/annotations-1.csv" \
    --out "C:/Users/Admin/Desktop/MEVA/phase9_manual_review"
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from survey_uhctd_events import (  # noqa: E402
    annotation_intervals, select_spans
)


def review_frame_numbers(span: dict, fps: float) -> list[int]:
    """Choose 6 exact 1-based frames; no media-specific offsets assumed."""
    if fps <= 0 or not math.isfinite(fps):
        raise ValueError("FPS must be positive")
    start, end = span["start"], span["end"]
    onset = span["onset"]
    if onset is None:
        fractions = (0., .08, .25, .50, .75, .95)
        picks = [start + round((end - start) * fraction) for fraction in fractions]
    else:
        picks = [
            onset - round(15 * fps), onset - 1, onset + round(2 * fps),
            onset + round(10 * fps), onset + round(40 * fps),
            onset + round(100 * fps),
        ]
    return [min(end, max(start, n)) for n in picks]


def read_frame(cap: cv2.VideoCapture, number: int) -> np.ndarray:
    if number < 1 or not cap.set(cv2.CAP_PROP_POS_FRAMES, number - 1):
        raise ValueError(f"Could not seek to frame {number}")
    observed = cap.get(cv2.CAP_PROP_POS_FRAMES)
    if abs(observed - (number - 1)) > 1:
        raise ValueError(f"Video seek imprecision at frame {number}")
    ok, frame = cap.read()
    if not ok:
        raise ValueError(f"Could not decode frame {number}")
    return frame


def contact_sheet(cap: cv2.VideoCapture, span: dict, fps: float,
                  cell_width: int = 400, cell_height: int = 310):
    picks = review_frame_numbers(span, fps)
    height, width = cell_height * 2, cell_width * 3
    canvas = np.full((height, width, 3), 246, dtype=np.uint8)
    labels = []
    for idx, frame_number in enumerate(picks):
        frame = read_frame(cap, frame_number)
        frame = cv2.resize(
            frame, (cell_width, cell_height - 32), interpolation=cv2.INTER_AREA
        )
        top, left = (idx // 3) * cell_height, (idx % 3) * cell_width
        canvas[top:top + cell_height - 32, left:left + cell_width] = frame
        instant = (frame_number - 1) / fps
        offset = (
            f"{(frame_number - span['onset']) / fps:+.1f}s"
            if span["onset"] is not None else "normal"
        )
        text = f"f={frame_number}  t={instant/3600:.3f}h  {offset}"
        cv2.putText(
            canvas, text, (left + 9, top + cell_height - 9),
            cv2.FONT_HERSHEY_SIMPLEX, .52, (20, 20, 20), 1, cv2.LINE_AA
        )
        labels.append({
            "frame": frame_number, "seconds": round(instant, 3),
            "offset_from_onset_seconds": (
                round((frame_number - span["onset"]) / fps, 3)
                if span["onset"] is not None else None
            ),
        })
    return canvas, labels


def export(video: Path, annotations: Path, out: Path, *,
           normal_window: int = 8, events_per_class: int = 4,
           normal_windows: int = 12) -> dict:
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise ValueError(f"Cannot open video {video}")
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if fps <= 0 or n_frames < 1:
            raise ValueError("Video lacks valid FPS and frame count")
        runs, labeled_count = annotation_intervals(annotations)
        if n_frames != labeled_count:
            raise ValueError("Video and annotation frame counts do not match")
        selections = select_spans(
            runs, fps, events_per_class, normal_windows, 120, 20, 90
        )
        chosen_name = f"normal_control_{normal_window}"
        selections = [
            x for x in selections if x["kind"] == 3 or x["name"] == chosen_name
        ]
        if len(selections) != events_per_class + 1:
            raise ValueError(f"Missing selected normal control {normal_window}")
        out.mkdir(parents=True, exist_ok=True)
        records = []
        for span in selections:
            sheet, frame_labels = contact_sheet(cap, span, fps)
            file_path = out / (span["name"] + "_review.jpg")
            if not cv2.imwrite(str(file_path), sheet,
                               [cv2.IMWRITE_JPEG_QUALITY, 92]):
                raise ValueError(f"Could not save {file_path}")
            records.append({
                "span": span["name"], "annotation_class": span["kind"],
                "extent": span["extent"],
                "onset_frame": span["onset"],
                "review_file": str(file_path.resolve()),
                "frames": frame_labels,
            })
            print(f"Saved {file_path.name}")
        summary = {
            "purpose": "MANUAL_REVIEW_NOT_MODEL_BENCHMARK",
            "source_video": str(video.resolve()),
            "fps": fps,
            "annotations": str(annotations.resolve()),
            "note": (
                "Manual review only. Dataset extent is a control parameter, "
                "not automatically literal visible area or guaranteed motion. "
                "Images remain local; honor dataset license and privacy."
            ),
            "selected": records,
        }
        (out / "movement_review_manifest.json").write_text(
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
    parser.add_argument("--normal-window", type=int, default=8)
    args = parser.parse_args()
    result = export(
        args.video, args.annotations, args.out,
        normal_window=args.normal_window,
    )
    print(f"Prepared {len(result['selected'])} contact sheets for review.")


if __name__ == "__main__":
    main()
