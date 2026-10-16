#!/usr/bin/env python3
"""Continuous, development-only camera shadow evaluation on UHCTD-style CSVs.

Unlike short-window surveys, both probes keep their state and camera reference
through the entire recording. The initial 10-second warmup MUST be annotated
normal. That dataset-known reference is not an officer-approved production
reference; neither a successful run nor a clean normal interval constitutes
independent camera qualification.

No frames, images, clips, per-person identifiers or raw labels are saved.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.services.camera_shadow_fusion import ShadowFusionProbe  # noqa: E402

CLASSES = {0: "normal", 1: "covered", 2: "defocused", 3: "moved"}
METHODS = ("spatial", "global", "fusion")


def checksum(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def ratio(num: int, den: int):
    return round(num / den, 6) if den else None


def _method_totals():
    return {m: Counter() for m in METHODS}


def _event(start: int, kind: int, extent: str, previous_alerts: dict):
    return {
        "class": CLASSES[kind], "start_frame": start, "end_frame": None,
        "extent_parameter": extent,
        "methods": {
            m: {
                "preexisting_at_onset": bool(previous_alerts[m]),
                "fresh_alert_frame": None,
                "any_review_samples": 0,
            } for m in METHODS
        },
    }


def evaluate(video: Path, labels: Path, *,
             sample_seconds: float = 1.0,
             preview_seconds: float | None = None) -> dict:
    if not math.isfinite(sample_seconds) or sample_seconds <= 0:
        raise ValueError("Sample interval must be positive and finite")
    if preview_seconds is not None and (
        not math.isfinite(preview_seconds) or preview_seconds <= 0
    ):
        raise ValueError("Preview seconds must be positive and finite")
    if not video.is_file() or not labels.is_file():
        raise ValueError("Both video and headerless annotation CSV are required")

    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise ValueError("Cannot open source video")
    try:
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        if not math.isfinite(fps) or fps <= 0 or frames < 1:
            raise ValueError("Invalid video FPS/frame count")
        step = max(1, round(fps * sample_seconds))
        interval = step / fps
        limit = frames if preview_seconds is None else min(
            frames, math.ceil(preview_seconds * fps)
        )
        full_run = limit == frames
        # An experimental warmup without annotated healthy footage is
        # invalid, even on development-only data.
        warmup_frames = math.ceil(10.0 * fps)
        if limit < warmup_frames:
            raise ValueError("Recording/preview must include at least 10 seconds")
        probe = ShadowFusionProbe()
        all_frames_by_class = Counter()
        sampled_by_class = Counter()
        unknown_by_class = Counter()
        warmup_by_class = Counter()
        method_counts = _method_totals()
        last_alert = {m: False for m in METHODS}
        last_label = None
        events = []
        active = None
        # Diagnostics only: do not store frames or reset the two probe states.
        normal_by_hour: dict[int, Counter] = {}
        normal_episode = None
        normal_episodes = []
        with labels.open("r", newline="", encoding="utf-8-sig") as stream:
            reader = csv.reader(stream, strict=True)
            for idx in range(limit):
                row = next(reader, None)
                if row is None or len(row) < 5:
                    raise ValueError(f"Annotation missing columns/frame {idx + 1}")
                try:
                    frame = int(row[0].strip())
                    kind = int(row[1].strip())
                except (ValueError, TypeError) as exc:
                    raise ValueError(f"Non-numeric frame/class at {idx + 1}") from exc
                if frame != idx + 1 or kind not in CLASSES:
                    raise ValueError(f"Annotation order/class mismatch at {idx + 1}")
                if idx < warmup_frames and kind != 0:
                    raise ValueError(
                        "Initial 10-second reference is not annotated normal"
                    )
                all_frames_by_class[CLASSES[kind]] += 1

                if kind != last_label:
                    if active is not None:
                        active["end_frame"] = frame - 1
                        events.append(active)
                        active = None
                    if kind != 0:
                        active = _event(frame, kind, row[2].strip(), last_alert)
                    last_label = kind

                # Keep video decoding sequential. Grab each frame; retrieve only
                # on the frozen evaluation cadence, preserving continuous state.
                if not capture.grab():
                    raise ValueError(f"Video ended before annotated frame {frame}")
                if idx % step:
                    continue
                ok, image = capture.retrieve()
                if not ok or image is None:
                    raise ValueError(f"Video decode failure at frame {frame}")
                observation = probe.observe(image, interval)
                method_alerts = {
                    "spatial": bool(observation["spatial_review"]),
                    "global": bool(observation["global_review"]),
                    "fusion": bool(observation["review_cue"]),
                }
                state = observation["evidence_status"]
                # Annotation-normal is only "no labeled tamper event".
                # Review origins and episode locations identify which periods
                # require independent inspection before changing any rule.
                if kind == 0:
                    hour = int(((frame - 1) / fps) // 3600)
                    hour_counts = normal_by_hour.setdefault(hour, Counter())
                    hour_counts["sampled_normal"] += 1
                    hour_counts["spatial_review"] += int(method_alerts["spatial"])
                    hour_counts["global_review"] += int(method_alerts["global"])
                    hour_counts["fusion_review"] += int(method_alerts["fusion"])
                    hour_counts["unknown_low_texture"] += int(
                        state == "UNKNOWN_LOW_TEXTURE"
                    )
                    hour_counts["global_quality_limited"] += int(
                        observation["global_quality_limited"]
                    )
                    hour_counts["fusion_spatial_source"] += int(
                        observation["decision"] == "SPATIAL_SCENE_REVIEW"
                    )
                    hour_counts["fusion_global_source"] += int(
                        observation["decision"] == "LOW_TEXTURE_GLOBAL_SCENE_REVIEW"
                    )
                    hour_counts["fusion_new_episode"] += int(
                        method_alerts["fusion"] and not last_alert["fusion"]
                    )
                if kind == 0 and method_alerts["fusion"]:
                    if normal_episode is None:
                        normal_episode = {
                            "start_frame": frame,
                            "end_frame": frame,
                            "samples": 0,
                            "spatial_cue_samples": 0,
                            "global_fallback_samples": 0,
                            "already_alerted_before_normal_span":
                                bool(last_alert["fusion"]),
                        }
                    normal_episode["end_frame"] = frame
                    normal_episode["samples"] += 1
                    normal_episode["spatial_cue_samples"] += int(
                        observation["decision"] == "SPATIAL_SCENE_REVIEW"
                    )
                    normal_episode["global_fallback_samples"] += int(
                        observation["decision"] == "LOW_TEXTURE_GLOBAL_SCENE_REVIEW"
                    )
                elif normal_episode is not None:
                    normal_episodes.append(normal_episode)
                    normal_episode = None
                sampled_by_class[CLASSES[kind]] += 1
                if state == "UNKNOWN_LOW_TEXTURE":
                    unknown_by_class[CLASSES[kind]] += 1
                elif state == "WARMUP":
                    warmup_by_class[CLASSES[kind]] += 1
                for method, alert in method_alerts.items():
                    counts = method_counts[method]
                    counts["sampled"] += 1
                    if kind == 0:
                        counts["normal_samples"] += 1
                        if alert:
                            counts["normal_review_samples"] += 1
                            if not last_alert[method]:
                                counts["new_normal_review_episodes"] += 1
                    else:
                        counts["positive_samples"] += 1
                        counts["positive_review_samples"] += int(alert)
                        if active is None:
                            raise RuntimeError("Missing active event")
                        info = active["methods"][method]
                        if alert:
                            info["any_review_samples"] += 1
                            if (not last_alert[method]
                                    and not info["preexisting_at_onset"]
                                    and info["fresh_alert_frame"] is None):
                                info["fresh_alert_frame"] = frame
                    last_alert[method] = alert

            if active is not None:
                active["end_frame"] = limit
                events.append(active)
            if normal_episode is not None:
                normal_episodes.append(normal_episode)
            if full_run and next(reader, None) is not None:
                raise ValueError("Annotation CSV has extra rows after video end")

    finally:
        capture.release()

    normal_hours = all_frames_by_class["normal"] / fps / 3600.0
    by_method = {}
    for method, counts in method_counts.items():
        per_class = {}
        for label in ("covered", "defocused", "moved"):
            group = [ev for ev in events if ev["class"] == label]
            fresh = [
                ev for ev in group
                if ev["methods"][method]["fresh_alert_frame"] is not None
            ]
            delays = [
                (ev["methods"][method]["fresh_alert_frame"] - ev["start_frame"]) / fps
                for ev in fresh
            ]
            per_class[label] = {
                "events": len(group),
                "fresh_alert_events": len(fresh),
                "fresh_alert_recall": ratio(len(fresh), len(group)),
                "events_preexisting_alert": sum(
                    ev["methods"][method]["preexisting_at_onset"]
                    for ev in group
                ),
                "events_with_any_alert_samples": sum(
                    ev["methods"][method]["any_review_samples"] > 0
                    for ev in group
                ),
                "mean_fresh_delay_seconds": (
                    round(sum(delays) / len(delays), 3) if delays else None
                ),
                "max_fresh_delay_seconds": round(max(delays), 3) if delays else None,
            }
        by_method[method] = {
            "normal_review_samples": counts["normal_review_samples"],
            "normal_samples": counts["normal_samples"],
            "normal_review_fraction": ratio(
                counts["normal_review_samples"], counts["normal_samples"]
            ),
            "new_normal_review_episodes": counts["new_normal_review_episodes"],
            "new_normal_review_episodes_per_normal_hour": (
                round(counts["new_normal_review_episodes"] / normal_hours, 6)
                if normal_hours else None
            ),
            "positive_review_samples": counts["positive_review_samples"],
            "positive_samples": counts["positive_samples"],
            "per_class": per_class,
        }
    hourly_rows = []
    for hour, counts in sorted(normal_by_hour.items()):
        hourly_rows.append({
            "hour_from_recording_start": hour,
            "normal_samples": counts["sampled_normal"],
            "spatial_review_samples": counts["spatial_review"],
            "global_review_samples": counts["global_review"],
            "fusion_review_samples": counts["fusion_review"],
            "fusion_review_fraction": ratio(
                counts["fusion_review"], counts["sampled_normal"]
            ),
            "fusion_from_spatial_samples": counts["fusion_spatial_source"],
            "fusion_from_global_fallback_samples": counts["fusion_global_source"],
            "global_quality_limited_samples": counts["global_quality_limited"],
            "unknown_low_texture_samples": counts["unknown_low_texture"],
            "new_fusion_review_episodes": counts["fusion_new_episode"],
        })
    episode_rows = [{
        **item,
        "start_seconds": round((item["start_frame"] - 1) / fps, 3),
        "end_seconds": round((item["end_frame"] - 1) / fps, 3),
        "sampled_review_seconds": round(item["samples"] * interval, 3),
    } for item in normal_episodes]
    event_rows = []
    for event in events:
        for method in METHODS:
            fields = event["methods"][method]
            found = fields["fresh_alert_frame"]
            event_rows.append({
                "class": event["class"],
                "start_frame": event["start_frame"],
                "end_frame": event["end_frame"],
                "extent_parameter": event["extent_parameter"],
                "method": method,
                "preexisting_at_onset": fields["preexisting_at_onset"],
                "fresh_review": found is not None,
                "fresh_delay_seconds": (
                    round((found - event["start_frame"]) / fps, 3)
                    if found is not None else ""
                ),
                "samples_with_review": fields["any_review_samples"],
            })

    return {
        "status": (
            "COMPLETE_CONTINUOUS_DEVELOPMENT_NOT_HELD_OUT"
            if full_run else "PREVIEW_ONLY_CONTINUOUS_DEVELOPMENT_NOT_HELD_OUT"
        ),
        "qualified": False,
        "production_integration": False,
        "reference_basis": "first_10_seconds_dataset_annotated_normal_not_officer_approved",
        "source_video": str(video.resolve()),
        "annotation_file": str(labels.resolve()),
        "source_video_sha256": checksum(video),
        "annotation_sha256": checksum(labels),
        "source_video_bytes": video.stat().st_size,
        "fps": fps, "total_source_frames": frames,
        "evaluated_frames": limit,
        "sample_step_frames": step,
        "effective_sample_seconds": interval,
        "normal_annotated_hours": round(normal_hours, 6),
        "frame_labels": dict(all_frames_by_class),
        "sampled_by_class": dict(sampled_by_class),
        "low_texture_unknown_by_class": dict(unknown_by_class),
        "warmup_samples_by_class": dict(warmup_by_class),
        "methods": by_method,
        "normal_review_hours": hourly_rows,
        "normal_review_episodes": episode_rows,
        "events": event_rows,
        "limitations": [
            "Day 3/4 are already-inspected development recordings, not independent hold-out",
            "First 10 seconds are annotated normal but not an independently approved camera reference",
            "No re-enrollment on changing lighting or camera conditions",
            "A review cue cannot prove camera movement or intentional tampering",
            "Unknown low texture is not a confident negative or evidence of usable footage",
            "Any short preview is ineligible for full-recording false-alarm claims",
            "Normal review episode counts are based on sampled state transitions",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True,
                        help="Output directory; numeric JSON/CSV only")
    parser.add_argument("--sample-seconds", type=float, default=1.0)
    parser.add_argument("--preview-seconds", type=float)
    args = parser.parse_args()
    result = evaluate(
        args.video.resolve(), args.annotations.resolve(),
        sample_seconds=args.sample_seconds, preview_seconds=args.preview_seconds,
    )
    args.out.mkdir(parents=True, exist_ok=True)
    summary_path = args.out / "continuous_shadow_summary.json"
    event_path = args.out / "continuous_shadow_events.csv"
    events = result.pop("events")
    episodes = result.pop("normal_review_episodes")
    normal_path = args.out / "continuous_shadow_normal_review_episodes.csv"
    with normal_path.open("w", newline="", encoding="utf-8") as stream:
        fields = [
            "start_frame", "end_frame", "samples", "spatial_cue_samples",
            "global_fallback_samples", "already_alerted_before_normal_span",
            "start_seconds", "end_seconds", "sampled_review_seconds",
        ]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(episodes)
    with event_path.open("w", newline="", encoding="utf-8") as stream:
        fields = [
            "class", "start_frame", "end_frame", "extent_parameter", "method",
            "preexisting_at_onset", "fresh_review", "fresh_delay_seconds",
            "samples_with_review",
        ]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(events)
    result["event_rows_csv"] = str(event_path.resolve())
    result["normal_review_episodes_csv"] = str(normal_path.resolve())
    result["normal_review_episodes_count"] = len(episodes)
    summary_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "qualified": result["qualified"],
        "normal_annotated_hours": result["normal_annotated_hours"],
        "low_texture_unknown_by_class": result["low_texture_unknown_by_class"],
        "methods": result["methods"],
        "summary_json": str(summary_path.resolve()),
        "events_csv": str(event_path.resolve()),
        "normal_review_episodes_csv": str(normal_path.resolve()),
    }, indent=2))


if __name__ == "__main__":
    main()
