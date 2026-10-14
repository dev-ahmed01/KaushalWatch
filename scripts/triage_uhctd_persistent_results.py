#!/usr/bin/env python3
"""Phase 10 shadow probe triage: numeric counterfactuals and *optional* local review.

Reads existing persistent_change_summary.json and persistent_change_samples.csv
WITHOUT rerunning the 24h video. Computes *post hoc* persistence-duration
sensitivity (exploratory only, never automatically tunes a detector).

Optionally opens the original local video and exports contact sheets for the
normal controls with false warnings. No images/video enter version control.

Example:
  python scripts/triage_uhctd_persistent_results.py \
    --summary "C:/Users/Admin/Desktop/MEVA/phase10_change_points/persistent_change_summary.json" \
    --samples "C:/Users/Admin/Desktop/MEVA/phase10_change_points/persistent_change_samples.csv" \
    --out "C:/Users/Admin/Desktop/MEVA/phase10_change_points/triage" \
    --video "C:/Users/Admin/Desktop/MEVA/video.avi"

Only share contact sheets if permitted under your dataset-use agreement.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

THRESHOLDS_SECONDS = (12.0, 15.0, 18.0, 20.0, 22.0, 25.0, 30.0)


def load_rows(samples_path: Path) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    with samples_path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        essential = {"span", "frame", "time_seconds", "post_onset",
                     "scene_correlation", "low_similarity", "changed_seconds",
                     "persistent_review"}
        if not reader.fieldnames or not essential.issubset(reader.fieldnames):
            raise ValueError("Not a Phase 10 persistent-change sample CSV")
        for row in reader:
            row["frame"] = int(row["frame"])
            row["time_seconds"] = float(row["time_seconds"])
            row["post_onset"] = row["post_onset"] == "True"
            row["low_similarity"] = row["low_similarity"] == "True"
            row["persistent_review"] = row["persistent_review"] == "True"
            row["changed_seconds"] = float(row["changed_seconds"])
            row["scene_correlation"] = (
                float(row["scene_correlation"])
                if row["scene_correlation"].strip() else None
            )
            grouped[row["span"]].append(row)
    if not grouped:
        raise ValueError("No sampled data")
    for name, rows in grouped.items():
        if any(b["frame"] <= a["frame"] for a, b in zip(rows, rows[1:])):
            raise ValueError(f"Non-increasing sample frame numbers for {name}")
    return dict(grouped)


def contiguous_episodes(rows: list[dict], key: str) -> list[dict]:
    episodes: list[dict] = []
    start = None
    for i, row in enumerate(rows):
        if bool(row[key]) and start is None:
            start = i
        if start is not None and (not bool(row[key]) or i == len(rows)-1):
            end = i - 1 if not bool(row[key]) else i
            episodes.append({
                "start_frame": rows[start]["frame"],
                "end_frame": rows[end]["frame"],
                "samples": end-start+1,
            })
            start = None
    return episodes


def analyse(summary: dict, grouped: dict[str, list[dict]]) -> dict:
    if summary.get("evaluation_status") != "PHASE10_SHADOW_DEVELOPMENT_NOT_HELD_OUT":
        raise ValueError("Results are not a Phase 10 shadow development survey")
    interval = float(summary.get("effective_sample_seconds", 0))
    if interval <= 0 or not math.isfinite(interval):
        raise ValueError("Invalid effective sample interval")
    expected = {row["span"] for row in summary["rows"]}
    if expected != set(grouped):
        raise ValueError("Summary and samples refer to different span sets")
    spans = []
    for meta in summary["rows"]:
        name = meta["span"]
        samples = grouped[name]
        flags = [v for v in samples if v["persistent_review"]]
        episodes = contiguous_episodes(samples, "persistent_review")
        low_episodes = contiguous_episodes(samples, "low_similarity")
        if len(flags) != int(meta["review_samples"]):
            raise ValueError(f"Summary/CSV review-count mismatch for {name}")
        spans.append({
            "span": name, "kind": meta["kind"],
            "sample_count": len(samples),
            "review_samples": len(flags),
            "false_review_episodes": (
                len(episodes) if int(meta["kind"]) == 0 else 0
            ),
            "review_episodes": episodes,
            "longest_low_similarity_seconds": round(
                max((r["samples"] for r in low_episodes), default=0)*interval, 3
            ),
            "minimum_scene_correlation": min(
                v["scene_correlation"] for v in samples
                if v["scene_correlation"] is not None
            ),
            "maximum_change_persistence_seconds": max(
                v["changed_seconds"] for v in samples
            ),
        })
    sensitivity = []
    for threshold in THRESHOLDS_SECONDS:
        moved = 0
        controls = 0
        normal_flagged = 0
        delays = []
        for meta in summary["rows"]:
            samples = grouped[meta["span"]]
            candidate = [r for r in samples if r["changed_seconds"] >= threshold]
            if meta["kind"] == 3:
                after = [r for r in candidate if r["post_onset"]]
                before = [r for r in candidate if not r["post_onset"]]
                if after and not before:
                    moved += 1
                    # Find onset time from reference metadata, not selected window start.
                    onset = int(meta["onset"])
                    fps = float(summary["fps"])
                    delays.append(round(
                        after[0]["time_seconds"] - (onset-1)/fps, 3
                    ))
            elif meta["kind"] == 0:
                if candidate:
                    controls += 1
                    normal_flagged += len(candidate)
        sensitivity.append({
            "confirmation_seconds": threshold,
            "moved_events_with_new_review": moved,
            "normal_controls_with_false_review": controls,
            "normal_false_review_samples": normal_flagged,
            "moved_detection_delays_seconds": delays,
        })
    return {
        "status": "POST_HOC_PHASE10_DIAGNOSTICS_NOT_INDEPENDENT_VALIDATION",
        "model_commit": summary.get("model_commit"),
        "source_video": summary.get("video"),
        "sampling_seconds": interval,
        "normal_review_samples": sum(
            v["review_samples"] for v in spans if v["kind"] == 0
        ),
        "normal_review_episodes": sum(
            v["false_review_episodes"] for v in spans if v["kind"] == 0
        ),
        "normal_review_seconds_equivalent": round(sum(
            v["review_samples"] for v in spans if v["kind"] == 0
        ) * interval, 3),
        "spans": spans,
        "threshold_sensitivity": sensitivity,
        "caveat": (
            "Threshold sensitivity is measured AFTER inspecting Day 3 data. "
            "Do not change production or shadow thresholds solely because "
            "a higher value suppresses two selected normal windows. "
            "This survey resets state per span, samples only limited video "
            "and cannot estimate full-day false alarm rate or true accuracy."
        ),
    }


def _frame(cap: cv2.VideoCapture, frame_no: int) -> np.ndarray:
    if not cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no-1):
        raise ValueError(f"Unable to seek video frame {frame_no}")
    ok, image = cap.read()
    if not ok:
        raise ValueError(f"Unable to decode frame {frame_no}")
    return image


def false_review_sheet(
    cap: cv2.VideoCapture, rows: list[dict], *, width: int = 400,
    cell_height: int = 300,
) -> tuple[np.ndarray, list[int]]:
    """Inspect first false warning and subsequent recovery using exact frames."""
    flagged = [i for i, item in enumerate(rows) if item["persistent_review"]]
    if not flagged:
        raise ValueError("Selected control has no false review to inspect")
    before = next(
        (i for i in range(flagged[0], -1, -1)
         if rows[i]["scene_correlation"] is not None
         and not rows[i]["low_similarity"]),
        0,
    )
    low = next(
        (i for i in range(before, flagged[0]+1) if rows[i]["low_similarity"]),
        before,
    )
    first, last = flagged[0], flagged[-1]
    recovered = next(
        (i for i in range(last+1, len(rows))
         if not rows[i]["low_similarity"]), len(rows)-1,
    )
    positions = [0, before, low, first, recovered, len(rows)-1]
    # Position text and source-frame numbers stay associated.
    images = []
    picks = []
    for i in positions:
        frame_no = rows[i]["frame"]
        picks.append(frame_no)
        image = cv2.resize(
            _frame(cap, frame_no), (width, cell_height-28),
            interpolation=cv2.INTER_AREA,
        )
        images.append(image)
    sheet = np.full((cell_height*2, width*3, 3), 245, dtype=np.uint8)
    captions = ("start", "before-change", "first-change",
                "first-review", "recovery", "end")
    for i, (image, frame_no, label) in enumerate(zip(images, picks, captions)):
        x, y = i % 3 * width, i // 3 * cell_height
        sheet[y:y+cell_height-28, x:x+width] = image
        cv2.putText(
            sheet, f"{label} f={frame_no}",
            (x+8, y+cell_height-8), cv2.FONT_HERSHEY_SIMPLEX,
            .53, (20, 20, 20), 1, cv2.LINE_AA,
        )
    return sheet, picks


def triage(summary_path: Path, sample_path: Path, out: Path,
           video: Path | None = None) -> dict:
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    groups = load_rows(sample_path)
    report = analyse(summary, groups)
    out.mkdir(parents=True, exist_ok=True)
    if video is not None:
        cap = cv2.VideoCapture(str(video))
        if not cap.isOpened():
            raise ValueError(f"Could not open video {video}")
        try:
            video_fps = float(cap.get(cv2.CAP_PROP_FPS))
            if abs(video_fps-float(summary["fps"])) > .01:
                raise ValueError("Source video FPS does not match shadow report")
            reviews = []
            for span in report["spans"]:
                if span["kind"] != 0 or span["review_samples"] == 0:
                    continue
                name = span["span"]
                sheet, picks = false_review_sheet(cap, groups[name])
                path = out / f"{name}_trigger_review.jpg"
                if not cv2.imwrite(str(path), sheet,
                                   [cv2.IMWRITE_JPEG_QUALITY, 90]):
                    raise ValueError(f"Could not write contact sheet {path}")
                reviews.append({"span": name, "frames": picks,
                                "image": str(path.resolve())})
            report["local_review_images"] = reviews
        finally:
            cap.release()
    (out / "shadow_false_review_triage.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--samples", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--video", type=Path)
    args = parser.parse_args()
    result = triage(args.summary, args.samples, args.out, args.video)
    print(json.dumps({
        "status": result["status"],
        "false_controls": [
            row["span"] for row in result["spans"]
            if row["kind"] == 0 and row["review_samples"]
        ],
        "false_review_samples": result["normal_review_samples"],
        "false_review_episodes": result["normal_review_episodes"],
        "threshold_sensitivity": result["threshold_sensitivity"],
        "local_review_images": result.get("local_review_images", []),
    }, indent=2))


if __name__ == "__main__":
    main()
