#!/usr/bin/env python3
"""Evaluate Camera Trust candidate: tampering alerts and video usability separately.

Requires Python with opencv-python, numpy and pydantic 2 installed.
Run from any directory; imports code from the enclosing KaushalWatch repo.
Do not use test labels to adjust thresholds after seeing held-out results.

Example:
  python scripts/evaluate_uhctd_camera_trust.py \
    --video "C:/Users/Admin/Desktop/MEVA/UHCTD_Day4/video.avi" \
    --annotations "C:/Users/Admin/Desktop/MEVA/UHCTD_Day4/annotations.csv" \
    --output-dir "C:/Users/Admin/Desktop/MEVA/UHCTD_Day4/evaluation"

Use --preview-seconds 60 for a format-only smoke check. Such a partial run
must never be reported as full held-out validation.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.services.camera_trust import CameraTrustState, assess_camera  # noqa: E402


NAMES = {0: "normal", 1: "covered", 2: "defocused", 3: "moved"}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git_head() -> str | None:
    result = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def score_recording(
    video: Path, annotations: Path, sample_seconds: float = 0.2,
    preview_seconds: float | None = None, verbose: bool = True,
) -> tuple[dict, list[dict]]:
    if sample_seconds <= 0 or not math.isfinite(sample_seconds):
        raise ValueError("sample_seconds must be finite and positive")
    if preview_seconds is not None and preview_seconds <= 0:
        raise ValueError("preview_seconds must be positive")
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise ValueError(f"Could not open video: {video}")
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if fps <= 0 or frame_count <= 0:
            raise ValueError("Video metadata must contain positive FPS and frame count")
        step = max(1, round(fps * sample_seconds))
        interval = step / fps
        limit = frame_count if preview_seconds is None else min(
            frame_count, math.ceil(preview_seconds * fps)
        )
        fully_evaluated = limit == frame_count
        total = Counter()
        by_label = {kind: Counter() for kind in NAMES}
        events = []
        current = None
        state = CameraTrustState()
        previous_tamper_alert = False
        false_alarm_episodes = 0
        normal_quality_suspensions = 0
        normal_reason_samples = Counter()
        tamper_reason_samples = Counter()
        started_at = time.monotonic()

        with annotations.open("r", encoding="utf-8-sig", newline="") as stream:
            labels = csv.reader(stream)
            for index in range(limit):
                row = next(labels, None)
                if row is None or len(row) < 5:
                    raise ValueError(f"Missing/incomplete annotations at frame {index+1}")
                try:
                    frame_number = int(row[0].strip())
                    label = int(row[1].strip())
                except ValueError as exc:
                    raise ValueError(f"Bad frame/class at CSV line {index+1}") from exc
                if frame_number != index + 1 or label not in NAMES:
                    raise ValueError(
                        f"Annotation/video mismatch: expected frame {index+1}, "
                        f"got frame {frame_number}, class {label}"
                    )

                if current is None or current["class"] != label:
                    if current is not None and current["class"] != 0:
                        events.append(current)
                    current = {
                        "class": label,
                        "start_frame": frame_number,
                        "end_frame": frame_number,
                        "detected_frame": None,
                        "first_any_alert_frame": None,
                        "preexisting_tamper_alert": previous_tamper_alert,
                        "flagged_samples": 0,
                    }
                else:
                    current["end_frame"] = frame_number

                # grab() traverses frames without decoding each intermediate
                # frame. retrieve() decodes only at the selected cadence.
                if not cap.grab():
                    raise ValueError(f"Unexpected video EOF at frame {index+1}")
                if index % step:
                    continue
                ret, frame = cap.retrieve()
                if not ret:
                    raise ValueError(f"Unable to decode sampled frame {index+1}")
                trust = assess_camera(
                    frame, state=state, sample_seconds=interval
                )
                alert = bool(trust.tamper_suspected)
                quality_alert = not trust.trusted
                if label == 0 and quality_alert:
                    normal_quality_suspensions += 1
                for reason in trust.reasons:
                    if label == 0:
                        normal_reason_samples[reason] += 1
                    else:
                        tamper_reason_samples[reason] += 1
                rising = alert and not previous_tamper_alert
                tampered = label != 0
                total["sampled"] += 1
                by_label[label]["sampled"] += 1
                if alert:
                    by_label[label]["alert"] += 1
                    total["predicted_alert"] += 1
                if tampered and alert:
                    total["tp"] += 1
                    current["flagged_samples"] += 1
                    if current["first_any_alert_frame"] is None:
                        current["first_any_alert_frame"] = frame_number
                    if rising and current["detected_frame"] is None:
                        current["detected_frame"] = frame_number
                elif tampered:
                    total["fn"] += 1
                elif alert:
                    total["fp"] += 1
                else:
                    total["tn"] += 1

                if label == 0 and rising:
                    false_alarm_episodes += 1
                previous_tamper_alert = alert
                if verbose and index and index % max(1, round(fps * 3600)) < step:
                    print(
                        f"Scanned {index / fps / 3600:.1f} hours "
                        f"({total['sampled']:,} sampled frames); "
                        f"elapsed {time.monotonic()-started_at:.0f}s",
                        flush=True,
                    )

            if fully_evaluated:
                extra = next(labels, None)
                if extra is not None:
                    raise ValueError(
                        "Annotation CSV has extra rows after video end; "
                        "verify the file pairing"
                    )
            if current is not None and current["class"] != 0:
                events.append(current)
        normal_hours = by_label[0]["sampled"] * interval / 3600.0
        tp, fp, tn, fn = (total[k] for k in ("tp", "fp", "tn", "fn"))
        div = lambda a, b: round(a / b, 6) if b else None
        detailed = []
        for event in events:
            name = NAMES[event["class"]]
            onset = (event["start_frame"] - 1) / fps
            detection = (
                (event["detected_frame"] - 1) / fps
                if event["detected_frame"] is not None else None
            )
            detailed.append({
                "class": name,
                "start_frame": event["start_frame"],
                "end_frame": event["end_frame"],
                "onset_seconds": round(onset, 3),
                "detected": detection is not None,
                "preexisting_tamper_alert": event["preexisting_tamper_alert"],
                "any_alert_during_event": event["first_any_alert_frame"] is not None,
                "first_alert_seconds": round(detection, 3) if detection is not None else "",
                "detection_delay_seconds": round(detection-onset, 3) if detection is not None else "",
                "flagged_samples": event["flagged_samples"],
            })

        event_per_class = {}
        for kind in (1, 2, 3):
            group = [e for e in detailed if e["class"] == NAMES[kind]]
            found = [e for e in group if e["detected"]]
            delays = sorted(float(e["detection_delay_seconds"]) for e in found)
            event_per_class[NAMES[kind]] = {
                "events": len(group),
                "events_detected": len(found),
                "events_with_preexisting_tamper_alert": sum(bool(e["preexisting_tamper_alert"]) for e in group),
                "events_with_any_alert": sum(bool(e["any_alert_during_event"]) for e in group),
                "event_recall": div(len(found), len(group)),
                "mean_detection_delay_seconds": div(sum(delays), len(delays)),
                "maximum_detection_delay_seconds": max(delays) if delays else None,
                "sampled_positive_frames": by_label[kind]["sampled"],
                "sampled_positive_frames_flagged": by_label[kind]["alert"],
                "positive_frame_recall": div(
                    by_label[kind]["alert"], by_label[kind]["sampled"]
                ),
            }
        summary = {
            "evaluation_status": (
                "COMPLETE_UNTOUCHED_RECORDING" if fully_evaluated
                else "PREVIEW_ONLY_NOT_HELD_OUT_VALIDATION"
            ),
            "model_commit": git_head(),
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "video_file": str(video.resolve()),
            "video_bytes": video.stat().st_size,
            "annotation_file": str(annotations.resolve()),
            "annotation_sha256": digest(annotations),
            "video_fps": fps,
            "video_frames": frame_count,
            "evaluated_frames": limit,
            "sample_step_frames": step,
            "effective_sample_seconds": interval,
            "positive_class": "suspected camera tampering (not poor visibility alone)",
            "tamper_event_detection_rule": "new rising alert within annotated interval; preexisting alerts do not count",
            "negative_class": "normal",
            "important": (
                "The detector produces trusted/untrusted, not a validated "
                "four-class diagnosis. Per-class figures report detection "
                "of each known tampering type, not four-class accuracy."
            ),
            "sampled_confusion": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
            "normal_quality_untrusted_samples": normal_quality_suspensions,
            "normal_quality_untrusted_fraction": div(normal_quality_suspensions, by_label[0]["sampled"]),
            "normal_untrusted_reasons": dict(normal_reason_samples),
            "tampered_untrusted_reasons": dict(tamper_reason_samples),
            "sampled_precision": div(tp, tp+fp),
            "sampled_recall": div(tp, tp+fn),
            "sampled_specificity": div(tn, tn+fp),
            "sampled_f1": div(2*tp, 2*tp+fp+fn),
            "normal_hours_sampled_equivalent": round(normal_hours, 5),
            "false_alarm_episodes": false_alarm_episodes,
            "false_alarm_episodes_per_normal_hour": div(
                false_alarm_episodes, normal_hours
            ),
            "false_positive_sample_fraction": div(fp, fp+tn),
            "per_tamper_class": event_per_class,
            "elapsed_wall_seconds": round(time.monotonic()-started_at, 2),
        }
        return summary, detailed
    finally:
        cap.release()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--annotations", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--sample-seconds", type=float, default=0.2)
    parser.add_argument(
        "--preview-seconds", type=float, default=None,
        help="Smoke check only: partial run, never full held-out evaluation",
    )
    args = parser.parse_args()
    if not args.video.is_file() or not args.annotations.is_file():
        parser.error("Video and annotations must be existing files")
    summary, events = score_recording(
        args.video, args.annotations, args.sample_seconds,
        args.preview_seconds,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_file = args.output_dir / "camera_trust_summary.json"
    csv_file = args.output_dir / "camera_trust_events.csv"
    json_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    with csv_file.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=[
                "class", "start_frame", "end_frame", "onset_seconds",
                "detected", "preexisting_tamper_alert", "any_alert_during_event", "first_alert_seconds",
                "detection_delay_seconds", "flagged_samples",
            ],
        )
        writer.writeheader()
        writer.writerows(events)
    print(json.dumps({
        "evaluation_status": summary["evaluation_status"],
        "sampled_confusion": summary["sampled_confusion"],
        "sampled_precision": summary["sampled_precision"],
        "sampled_recall": summary["sampled_recall"],
        "false_alarms_per_normal_hour": summary["false_alarm_episodes_per_normal_hour"],
        "per_tamper_class": summary["per_tamper_class"],
        "summary_json": str(json_file),
        "events_csv": str(csv_file),
    }, indent=2))


if __name__ == "__main__":
    main()
