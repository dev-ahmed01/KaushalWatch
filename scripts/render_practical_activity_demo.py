from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.services.activity_evidence import (\n    TemporalActivityGate,\n    roi_motion_fraction,\n    worker_motion_fraction,\n)
from app.services.track_presence import TrackObservation, TrackPresenceRegistry


def load_zones(path: Path, scenario: str) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    zones = payload.get(scenario)
    if not isinstance(zones, list) or not zones:
        raise ValueError(f"No work-zone list found for scenario {scenario!r}")
    return zones


def zone_name(zone: dict, index: int) -> str:
    return str(zone.get("zone_id") or f"work_zone_{index + 1}")


def zone_rect(zone: dict) -> tuple[int, int, int, int]:
    x1 = int(zone["x"])
    y1 = int(zone["y"])
    return x1, y1, x1 + int(zone["w"]), y1 + int(zone["h"])


def intersection_ratio(box: tuple[int, int, int, int], zone: dict) -> float:
    x1, y1, x2, y2 = box
    zx1, zy1, zx2, zy2 = zone_rect(zone)
    ix1, iy1 = max(x1, zx1), max(y1, zy1)
    ix2, iy2 = min(x2, zx2), min(y2, zy2)
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    return (iw * ih) / max(1, (x2 - x1) * (y2 - y1))


def assign_zone(
    box: tuple[int, int, int, int],
    zones: list[dict],
    minimum_overlap: float,
) -> str | None:
    x1, y1, x2, y2 = box
    cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0

    best_zone: str | None = None
    best_score = 0.0

    for index, zone in enumerate(zones):
        zx1, zy1, zx2, zy2 = zone_rect(zone)
        overlap = intersection_ratio(box, zone)
        centre_inside = zx1 <= cx <= zx2 and zy1 <= cy <= zy2
        score = 1.0 + overlap if centre_inside else overlap
        if score >= minimum_overlap and score > best_score:
            best_score = score
            best_zone = zone_name(zone, index)

    return best_zone


def draw_label(
    frame: np.ndarray,
    text: str,
    x: int,
    y: int,
    color: tuple[int, int, int],
    scale: float = 0.48,
) -> None:
    font = cv2.FONT_HERSHEY_SIMPLEX
    thickness = 1
    (tw, th), baseline = cv2.getTextSize(text, font, scale, thickness)
    x = max(0, min(x, frame.shape[1] - tw - 10))
    y = max(th + 8, min(y, frame.shape[0] - baseline - 3))

    cv2.rectangle(
        frame,
        (x, y - th - 7),
        (x + tw + 8, y + baseline + 2),
        (18, 18, 18),
        -1,
    )
    cv2.putText(
        frame,
        text,
        (x + 4, y - 3),
        font,
        scale,
        color,
        thickness,
        cv2.LINE_AA,
    )


def draw_panel(
    frame: np.ndarray,
    lines: list[tuple[str, tuple[int, int, int]]],
) -> None:
    width = min(455, frame.shape[1] - 20)
    line_height = 27
    height = 18 + line_height * len(lines)
    overlay = frame.copy()
    cv2.rectangle(overlay, (10, 10), (10 + width, 10 + height), (10, 10, 10), -1)
    cv2.addWeighted(overlay, 0.76, frame, 0.24, 0, frame)

    y = 37
    for index, (line, color) in enumerate(lines):
        cv2.putText(
            frame,
            line,
            (22, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.60,
            color,
            2 if index == 0 else 1,
            cv2.LINE_AA,
        )
        y += line_height


def authorization_text(value: str) -> str:
    if value == "valid":
        return "VALID"
    if value == "absent":
        return "NOT FOUND"
    return "UNKNOWN"


def decision_text(activity: bool, authorization: str) -> str:
    if not activity:
        return "OBSERVING"
    if authorization == "valid":
        return "AUTHORIZED PRACTICAL ACTIVITY"
    if authorization == "absent":
        return "UNAUTHORIZED PRACTICAL ACTIVITY"
    return "ACTIVITY REVIEW REQUIRED"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Render KaushalWatch practical-work evidence using stable anonymous "
            "tracks plus sustained motion inside configured work cells."
        )
    )
    parser.add_argument("--video", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--zones-json", required=True)
    parser.add_argument("--scenario", required=True)
    parser.add_argument(
        "--authorization",
        choices=["valid", "absent", "unknown"],
        default="unknown",
        help="External work-order/training-schedule state; never inferred from appearance.",
    )
    parser.add_argument("--csv-output")
    parser.add_argument("--summary-output")
    parser.add_argument("--model", default="yolo11n.pt")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--conf", type=float, default=0.35)
    parser.add_argument("--iou", type=float, default=0.50)
    parser.add_argument("--tracker", default="bytetrack.yaml")
    parser.add_argument("--confirm-seconds", type=float, default=1.0)
    parser.add_argument("--register-seconds", type=float, default=2.0)
    parser.add_argument("--grace-seconds", type=float, default=0.8)
    parser.add_argument("--zone-overlap", type=float, default=0.15)
    parser.add_argument("--activity-window-seconds", type=float, default=1.0)
    parser.add_argument("--activity-required-ratio", type=float, default=0.60)
    parser.add_argument(\n        "--motion-threshold",\n        type=float,\n        default=0.02,\n        help="Minimum worker-box motion fraction for one positive activity sample.",\n    )
    parser.add_argument("--motion-pixel-delta", type=int, default=18)
    parser.add_argument(
        "--mode",
        choices=["demo", "debug"],
        default="demo",
    )
    parser.add_argument("--show", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise SystemExit(
            "Ultralytics is required. Install backend/requirements-yolo-demo.txt."
        ) from exc

    video_path = Path(args.video).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    zones_path = Path(args.zones_json).expanduser().resolve()
    csv_path = (
        Path(args.csv_output).expanduser().resolve()
        if args.csv_output
        else output_path.with_suffix(".csv")
    )
    summary_path = (
        Path(args.summary_output).expanduser().resolve()
        if args.summary_output
        else output_path.with_suffix(".summary.json")
    )

    if not video_path.exists():
        raise SystemExit(f"Video not found: {video_path}")
    if not zones_path.exists():
        raise SystemExit(f"Zone file not found: {zones_path}")

    zones = load_zones(zones_path, args.scenario)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise SystemExit(f"Could not open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    writer = cv2.VideoWriter(
        str(output_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )
    if not writer.isOpened():
        raise SystemExit(f"Could not create output video: {output_path}")

    presence = TrackPresenceRegistry(
        confirmation_seconds=args.confirm_seconds,
        registration_seconds=args.register_seconds,
        grace_seconds=args.grace_seconds,
    )

    activity_window_frames = max(1, int(round(args.activity_window_seconds * fps)))
    activity_gates = {
        zone_name(zone, index): TemporalActivityGate(
            window_frames=activity_window_frames,
            motion_fraction_threshold=args.motion_threshold,
            required_positive_ratio=args.activity_required_ratio,
        )
        for index, zone in enumerate(zones)
    }

    model = YOLO(args.model)
    stream = model.track(
        source=str(video_path),
        stream=True,
        persist=True,
        tracker=args.tracker,
        classes=[0],
        conf=args.conf,
        iou=args.iou,
        imgsz=args.imgsz,
        verbose=False,
    )

    frame_rows: list[dict] = []
    previous_frame: np.ndarray | None = None
    zone_motion_scores: dict[str, list[float]] = defaultdict(list)
    zone_active_frames: dict[str, int] = defaultdict(int)
    zone_presence_frames: dict[str, int] = defaultdict(int)
    zone_active_since: dict[str, float | None] = {name: None for name in activity_gates}
    first_activity_time: float | None = None
    practical_activity_frames = 0
    frame_no = 0

    try:
        for result in stream:
            timestamp = frame_no / fps
            source_frame = result.orig_img.copy()
            frame = source_frame.copy()

            boxes = []
            confidences = []
            track_ids = []

            if len(result.boxes):
                boxes = result.boxes.xyxy.cpu().numpy().tolist()
                confidences = result.boxes.conf.cpu().numpy().tolist()
                track_ids = (
                    result.boxes.id.int().cpu().tolist()
                    if result.boxes.id is not None
                    else [None] * len(boxes)
                )

            current_ids: set[int] = set()
            observations: list[TrackObservation] = []

            for index, raw_box in enumerate(boxes):
                track_id = track_ids[index] if index < len(track_ids) else None
                if track_id is None:
                    continue

                x1, y1, x2, y2 = [int(round(value)) for value in raw_box]
                box = (x1, y1, x2, y2)
                zone_id = assign_zone(box, zones, args.zone_overlap)
                current_ids.add(int(track_id))
                observations.append(
                    TrackObservation(
                        track_id=int(track_id),
                        x1=x1,
                        y1=y1,
                        x2=x2,
                        y2=y2,
                        confidence=float(confidences[index]),
                        zone_id=zone_id,
                    )
                )

            presence.update(timestamp, observations)

            # Only currently visible attendance-registered tracks may contribute
            # to practical-work evidence. Grace-held tracks remain useful for
            # attendance continuity but cannot create activity while invisible.
            registered_by_zone: dict[str, list] = defaultdict(list)
            for track in presence.registered_tracks:
                if track.track_id in current_ids and track.zone_id:
                    registered_by_zone[track.zone_id].append(track)

            zone_decisions = {}
            zone_diagnostics = {}
            for index, zone in enumerate(zones):
                name = zone_name(zone, index)
                rect = zone_rect(zone)

                # Whole-zone motion is retained only as a diagnostic. Large work
                # cells dilute local operator movement, so the activity gate uses
                # motion inside currently visible registered worker boxes instead.
                zone_motion = roi_motion_fraction(
                    previous_frame,
                    source_frame,
                    rect,
                    pixel_delta_threshold=args.motion_pixel_delta,
                )
                worker_boxes = [track.bbox for track in registered_by_zone.get(name, [])]
                worker_motion = worker_motion_fraction(
                    previous_frame,
                    source_frame,
                    worker_boxes,
                    pixel_delta_threshold=args.motion_pixel_delta,
                )

                worker_present = bool(worker_boxes)
                decision = activity_gates[name].update(worker_present, worker_motion)
                zone_decisions[name] = decision
                zone_diagnostics[name] = {
                    "worker_motion": worker_motion,
                    "zone_motion": zone_motion,
                }
                worker_motion_scores[name].append(worker_motion)
                zone_motion_scores[name].append(zone_motion)

                if worker_present:
                    zone_presence_frames[name] += 1
                if decision.active:
                    zone_active_frames[name] += 1
                    if zone_active_since[name] is None:
                        zone_active_since[name] = timestamp
                else:
                    zone_active_since[name] = None

            practical_activity = any(d.active for d in zone_decisions.values())
            if practical_activity:
                practical_activity_frames += 1
                if first_activity_time is None:
                    first_activity_time = timestamp

            active_names = [name for name, d in zone_decisions.items() if d.active]

            # Work-cell outlines are thin and semantic: cyan watching, green valid
            # activity, red unauthorized activity.
            for index, zone in enumerate(zones):
                name = zone_name(zone, index)
                rect = zone_rect(zone)
                decision = zone_decisions[name]
                worker_count = len(registered_by_zone.get(name, []))

                if decision.active and args.authorization == "absent":
                    color = (0, 0, 255)
                elif decision.active:
                    color = (0, 220, 0)
                else:
                    color = (255, 180, 0)

                cv2.rectangle(frame, (rect[0], rect[1]), (rect[2], rect[3]), color, 2)

                active_for = (
                    timestamp - zone_active_since[name]
                    if zone_active_since[name] is not None
                    else 0.0
                )
                state = "ACTIVE" if decision.active else "WATCHING"
                label = (
                    f"{name} | {worker_count} stable | {state}"
                    + (f" {active_for:.1f}s" if decision.active else "")
                )
                draw_label(frame, label, rect[0] + 4, rect[1] + 24, color)

            # Stable person timer. Tentative detections are intentionally not
            # promoted into attendance-style labels.
            for track in presence.active_tracks:
                currently_seen = track.track_id in current_ids

                if not track.confirmed:
                    if args.mode == "debug" and currently_seen:
                        cv2.rectangle(
                            frame,
                            (track.x1, track.y1),
                            (track.x2, track.y2),
                            (145, 145, 145),
                            1,
                        )
                    continue

                if track.registered:
                    color = (0, 220, 0)
                    label = f"A{track.track_id:02d} | {track.visible_seconds:.1f}s"
                    if track.zone_id:
                        label += f" | zone {track.zone_dwell_seconds:.1f}s"
                else:
                    color = (0, 220, 255)
                    label = f"A{track.track_id:02d} VERIFYING | {track.visible_seconds:.1f}s"

                if not currently_seen:
                    color = (0, 165, 255)
                    label = f"A{track.track_id:02d} HOLD | {track.missed_seconds:.1f}s"

                cv2.rectangle(
                    frame,
                    (track.x1, track.y1),
                    (track.x2, track.y2),
                    color,
                    2,
                )
                draw_label(frame, label, track.x1, max(20, track.y1 - 4), color)

            auth = authorization_text(args.authorization)
            work_state = "CONFIRMED" if practical_activity else "VERIFYING"
            final_decision = decision_text(practical_activity, args.authorization)

            if final_decision == "UNAUTHORIZED PRACTICAL ACTIVITY":
                decision_color = (0, 0, 255)
            elif final_decision == "AUTHORIZED PRACTICAL ACTIVITY":
                decision_color = (0, 220, 0)
            else:
                decision_color = (255, 255, 255)

            panel_lines = [
                ("KaushalWatch | Practical Work Evidence", (0, 255, 255)),
                (f"Time: {timestamp:.2f}s", (255, 255, 255)),
                (f"Stable workers: {presence.registered_count}", (255, 255, 255)),
                (
                    f"Active work cells: {len(active_names)}/{len(zones)}",
                    (255, 255, 255),
                ),
                (f"Work activity: {work_state}", (255, 255, 255)),
                (f"Training authorization: {auth}", (255, 255, 255)),
                (f"Decision: {final_decision}", decision_color),
            ]
            if args.mode == "debug":
                panel_lines.extend(
                    [
                        (f"Raw detections: {len(boxes)}", (180, 180, 180)),
                        (f"Verifying tracks: {presence.candidate_count}", (180, 180, 180)),
                    ]
                )
            draw_panel(frame, panel_lines)

            writer.write(frame)

            row = {
                "frame": frame_no,
                "timestamp_sec": round(timestamp, 3),
                "raw_detections": len(boxes),
                "stable_workers": presence.registered_count,
                "practical_activity": practical_activity,
                "authorization": args.authorization,
                "decision": final_decision,
            }
            for index, zone in enumerate(zones):
                name = zone_name(zone, index)
                decision = zone_decisions[name]
                row[f"{name}_stable_workers"] = len(registered_by_zone.get(name, []))
                row[f"{name}_worker_motion_fraction"] = round(
                    zone_diagnostics[name]["worker_motion"], 6
                )
                row[f"{name}_zone_motion_fraction"] = round(
                    zone_diagnostics[name]["zone_motion"], 6
                )
                row[f"{name}_motion_positive_ratio"] = round(decision.positive_ratio, 4)
                row[f"{name}_active"] = decision.active
            frame_rows.append(row)

            previous_frame = source_frame
            frame_no += 1

            if args.show:
                cv2.imshow("KaushalWatch practical activity", frame)
                if cv2.waitKey(1) & 0xFF in (27, ord("q")):
                    break
    finally:
        writer.release()
        if args.show:
            cv2.destroyAllWindows()

    if not frame_rows:
        raise SystemExit("No frames processed")

    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer_csv = csv.DictWriter(handle, fieldnames=frame_rows[0].keys())
        writer_csv.writeheader()
        writer_csv.writerows(frame_rows)

    zone_summaries = []
    for index, zone in enumerate(zones):
        name = zone_name(zone, index)
        worker_scores = np.asarray(worker_motion_scores[name], dtype=float)
        zone_scores = np.asarray(zone_motion_scores[name], dtype=float)
        zone_summaries.append(
            {
                "zone_id": name,
                "worker_motion_fraction_p50": float(np.percentile(worker_scores, 50)),
                "worker_motion_fraction_p90": float(np.percentile(worker_scores, 90)),
                "worker_motion_fraction_p95": float(np.percentile(worker_scores, 95)),
                "zone_motion_fraction_p50": float(np.percentile(zone_scores, 50)),
                "zone_motion_fraction_p90": float(np.percentile(zone_scores, 90)),
                "zone_motion_fraction_p95": float(np.percentile(zone_scores, 95)),
                "registered_worker_presence_fraction": (
                    zone_presence_frames[name] / frame_no
                ),
                "activity_fraction": zone_active_frames[name] / frame_no,
            }
        )

    summary = {
        "source_video": str(video_path),
        "output_video": str(output_path),
        "scenario": args.scenario,
        "authorization": args.authorization,
        "frames_processed": frame_no,
        "fps": fps,
        "detector": {
            "model": args.model,
            "imgsz": args.imgsz,
            "confidence": args.conf,
            "nms_iou": args.iou,
            "tracker": args.tracker,
        },
        "presence_policy": {
            "confirmation_seconds": args.confirm_seconds,
            "registration_seconds": args.register_seconds,
            "grace_seconds": args.grace_seconds,
        },
        "activity_policy": {
            "window_seconds": args.activity_window_seconds,
            "window_frames": activity_window_frames,
            "required_positive_ratio": args.activity_required_ratio,
            "motion_fraction_threshold": args.motion_threshold,
            "pixel_delta_threshold": args.motion_pixel_delta,
            "rule": (
                "A work cell is active only when at least one currently visible, "
                "attendance-registered anonymous track occupies the cell and "
                "worker-centric visual motion persists for the configured temporal ratio."
            ),
        },
        "practical_activity_fraction": practical_activity_frames / frame_no,
        "first_practical_activity_time_sec": first_activity_time,
        "work_cells": zone_summaries,
        "interpretation_note": (
            "Practical activity is a worker-centric visual motion proxy, not task "
            "recognition, skill-quality assessment, safety classification, mechanical "
            "diagnosis, or worker identity. Whole-zone motion is diagnostic only. "
            "Authorization is external scenario/work-order state."
        ),
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))
    print(f"Frame CSV: {csv_path}")
    print(f"Annotated video: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
