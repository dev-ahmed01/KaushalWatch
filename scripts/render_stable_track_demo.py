from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.services.track_presence import TrackObservation, TrackPresenceRegistry


def load_zones(path: Path | None, scenario: str | None) -> list[dict]:
    if path is None:
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if scenario is None:
        if isinstance(payload, list):
            return payload
        raise ValueError("--scenario is required when the zone JSON contains scenarios")
    zones = payload.get(scenario)
    if not isinstance(zones, list):
        raise ValueError(f"No zone list found for scenario {scenario!r}")
    return zones


def intersection_ratio(box: tuple[int, int, int, int], zone: dict) -> float:
    x1, y1, x2, y2 = box
    zx1, zy1 = int(zone["x"]), int(zone["y"])
    zx2 = zx1 + int(zone["w"])
    zy2 = zy1 + int(zone["h"])

    ix1, iy1 = max(x1, zx1), max(y1, zy1)
    ix2, iy2 = min(x2, zx2), min(y2, zy2)
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    intersection = iw * ih
    person_area = max(1, (x2 - x1) * (y2 - y1))
    return intersection / person_area


def assign_zone(
    box: tuple[int, int, int, int],
    zones: list[dict],
    minimum_overlap: float,
) -> str | None:
    x1, y1, x2, y2 = box
    cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0

    best_zone: str | None = None
    best_score = 0.0

    for index, zone in enumerate(zones, 1):
        zx1, zy1 = int(zone["x"]), int(zone["y"])
        zx2 = zx1 + int(zone["w"])
        zy2 = zy1 + int(zone["h"])
        overlap = intersection_ratio(box, zone)
        centre_inside = zx1 <= cx <= zx2 and zy1 <= cy <= zy2

        score = 1.0 + overlap if centre_inside else overlap
        if score >= minimum_overlap and score > best_score:
            best_score = score
            best_zone = str(zone.get("zone_id") or f"work_zone_{index}")

    return best_zone


def draw_label(
    frame,
    text: str,
    x: int,
    y: int,
    color: tuple[int, int, int],
) -> None:
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.52
    thickness = 1
    (tw, th), baseline = cv2.getTextSize(text, font, scale, thickness)
    x = max(0, min(x, frame.shape[1] - tw - 8))
    y = max(th + 8, y)
    cv2.rectangle(
        frame,
        (x, y - th - 7),
        (x + tw + 7, y + baseline + 2),
        (20, 20, 20),
        -1,
    )
    cv2.putText(
        frame,
        text,
        (x + 3, y - 3),
        font,
        scale,
        color,
        thickness,
        cv2.LINE_AA,
    )


def draw_panel(frame, lines: list[str]) -> None:
    width = min(420, frame.shape[1] - 20)
    line_h = 25
    height = 18 + line_h * len(lines)
    overlay = frame.copy()
    cv2.rectangle(overlay, (10, 10), (10 + width, 10 + height), (12, 12, 12), -1)
    cv2.addWeighted(overlay, 0.72, frame, 0.28, 0, frame)

    y = 35
    for index, line in enumerate(lines):
        color = (255, 255, 255) if index else (0, 255, 255)
        cv2.putText(
            frame,
            line,
            (22, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.58,
            color,
            2 if index == 0 else 1,
            cv2.LINE_AA,
        )
        y += line_h


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Render anonymous track maturity timers and suppress transient "
            "person detections before attendance registration."
        )
    )
    parser.add_argument("--video", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--csv-output")
    parser.add_argument("--summary-output")
    parser.add_argument("--zones-json")
    parser.add_argument("--scenario")
    parser.add_argument("--model", default="yolo11n.pt")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--conf", type=float, default=0.35)
    parser.add_argument("--iou", type=float, default=0.50)
    parser.add_argument("--tracker", default="bytetrack.yaml")
    parser.add_argument("--confirm-seconds", type=float, default=1.0)
    parser.add_argument("--register-seconds", type=float, default=2.0)
    parser.add_argument("--grace-seconds", type=float, default=0.8)
    parser.add_argument("--zone-overlap", type=float, default=0.15)
    parser.add_argument(
        "--mode",
        choices=["demo", "debug"],
        default="demo",
        help="demo hides most raw tracker noise; debug shows tentative tracks too",
    )
    parser.add_argument("--show", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise SystemExit(
            "Ultralytics is required for this renderer. Install "
            "backend/requirements-yolo-demo.txt first."
        ) from exc

    video_path = Path(args.video).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
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
    zones_path = (
        Path(args.zones_json).expanduser().resolve()
        if args.zones_json
        else None
    )
    zones = load_zones(zones_path, args.scenario)

    if not video_path.exists():
        raise SystemExit(f"Video not found: {video_path}")

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

    registry = TrackPresenceRegistry(
        confirmation_seconds=args.confirm_seconds,
        registration_seconds=args.register_seconds,
        grace_seconds=args.grace_seconds,
    )
    model = YOLO(args.model)

    frame_rows: list[dict] = []
    registered_session_ids: set[int] = set()
    frame_no = 0

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

    try:
        for result in stream:
            timestamp = frame_no / fps
            frame = result.orig_img.copy()

            boxes = []
            confidences = []
            track_ids = []

            if len(result.boxes):
                boxes = result.boxes.xyxy.cpu().numpy().tolist()
                confidences = result.boxes.conf.cpu().numpy().tolist()
                if result.boxes.id is not None:
                    track_ids = result.boxes.id.int().cpu().tolist()
                else:
                    track_ids = [None] * len(boxes)

            current_ids: set[int] = set()
            observations: list[TrackObservation] = []

            for index, raw_box in enumerate(boxes):
                track_id = track_ids[index] if index < len(track_ids) else None
                if track_id is None:
                    continue

                x1, y1, x2, y2 = [int(round(value)) for value in raw_box]
                confidence = float(confidences[index])
                box = (x1, y1, x2, y2)
                zone_id = assign_zone(box, zones, args.zone_overlap) if zones else None

                current_ids.add(int(track_id))
                observations.append(
                    TrackObservation(
                        track_id=int(track_id),
                        x1=x1,
                        y1=y1,
                        x2=x2,
                        y2=y2,
                        confidence=confidence,
                        zone_id=zone_id,
                    )
                )

            registry.update(timestamp, observations)

            for track in registry.registered_tracks:
                registered_session_ids.add(track.track_id)

            transient_rejected = sum(
                1
                for track in registry.tracks
                if not track.active and not track.registered
            )

            # Thin work-cell outlines: contextual, not dominant.
            for index, zone in enumerate(zones, 1):
                x1, y1 = int(zone["x"]), int(zone["y"])
                x2 = x1 + int(zone["w"])
                y2 = y1 + int(zone["h"])
                cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 180, 0), 1)
                draw_label(
                    frame,
                    str(zone.get("zone_id") or f"Z{index}"),
                    x1 + 4,
                    y1 + 22,
                    (255, 180, 0),
                )

            # Draw registry state rather than treating every raw detection equally.
            for track in registry.active_tracks:
                currently_seen = track.track_id in current_ids

                if track.registered:
                    color = (0, 220, 0)
                    state_label = "PRESENT"
                elif track.confirmed:
                    color = (0, 220, 255)
                    state_label = "CONFIRMED"
                else:
                    color = (160, 160, 160)
                    state_label = "VERIFYING"

                if not currently_seen:
                    # Keep the logical person through a brief detector miss, but make
                    # the hold state visually explicit.
                    color = (0, 165, 255)
                    state_label = f"HOLD {track.missed_seconds:.1f}s"

                if args.mode == "demo" and not track.confirmed and currently_seen:
                    # Tentative detections stay visible as subtle boxes but do not
                    # receive an attendance-style timer label.
                    cv2.rectangle(
                        frame,
                        (track.x1, track.y1),
                        (track.x2, track.y2),
                        color,
                        1,
                    )
                    continue

                cv2.rectangle(
                    frame,
                    (track.x1, track.y1),
                    (track.x2, track.y2),
                    color,
                    2,
                )

                timer = f"{track.visible_seconds:.1f}s"
                label = f"A{track.track_id:02d} {state_label} {timer}"
                if track.zone_id:
                    label += f" | {track.zone_id} {track.zone_dwell_seconds:.1f}s"

                draw_label(
                    frame,
                    label,
                    track.x1,
                    max(20, track.y1 - 4),
                    color,
                )

            panel_lines = [
                "KaushalWatch | anonymous stable presence",
                f"Time: {timestamp:.2f}s",
                f"Raw detections: {len(boxes)}",
                f"Verifying: {registry.candidate_count}",
                f"Confirmed tracks: {registry.confirmed_count}",
                f"Stable occupancy: {registry.registered_count}",
                f"Transient tracks rejected: {transient_rejected}",
            ]
            draw_panel(frame, panel_lines)

            writer.write(frame)

            frame_rows.append(
                {
                    "frame": frame_no,
                    "timestamp_sec": round(timestamp, 3),
                    "raw_detections": len(boxes),
                    "verifying_tracks": registry.candidate_count,
                    "confirmed_tracks": registry.confirmed_count,
                    "stable_occupancy": registry.registered_count,
                    "transient_tracks_rejected": transient_rejected,
                }
            )

            if args.show:
                cv2.imshow("KaushalWatch stable tracks", frame)
                key = cv2.waitKey(1) & 0xFF
                if key in (27, ord("q")):
                    break

            frame_no += 1
    finally:
        writer.release()
        if args.show:
            cv2.destroyAllWindows()

    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer_csv = csv.DictWriter(handle, fieldnames=frame_rows[0].keys())
        writer_csv.writeheader()
        writer_csv.writerows(frame_rows)

    transient_tracks = [
        track
        for track in registry.tracks
        if not track.registered
    ]
    summary = {
        "source_video": str(video_path),
        "output_video": str(output_path),
        "frames_processed": frame_no,
        "fps": fps,
        "model": args.model,
        "imgsz": args.imgsz,
        "confidence": args.conf,
        "nms_iou": args.iou,
        "tracker": args.tracker,
        "confirmation_seconds": args.confirm_seconds,
        "attendance_registration_seconds": args.register_seconds,
        "grace_seconds": args.grace_seconds,
        "registered_track_sessions": len(registered_session_ids),
        "transient_track_sessions": len(transient_tracks),
        "privacy_note": (
            "Axx labels are anonymous session-local tracker IDs, not identities. "
            "registered_track_sessions must not be interpreted as unique-person "
            "identity attendance across fragmented tracks."
        ),
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))
    print(f"Frame CSV: {csv_path}")
    print(f"Annotated video: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
