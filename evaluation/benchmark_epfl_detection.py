from __future__ import annotations

import argparse
import csv
import json
import os
import shlex
import sys
from collections import defaultdict
from pathlib import Path

import cv2

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from app.services.person_detector import Detection, build_person_detector


def parse_epfl_gt(path: Path) -> dict[int, list[tuple[int, int, int, int]]]:
    frames: dict[int, list[tuple[int, int, int, int]]] = defaultdict(list)
    for raw in path.read_text().splitlines():
        raw = raw.strip()
        if not raw:
            continue
        cols = shlex.split(raw)
        if len(cols) < 10:
            continue
        # id xmin ymin xmax ymax frame lost occluded generated label
        xmin, ymin, xmax, ymax = map(lambda x: int(float(x)), cols[1:5])
        frame = int(float(cols[5]))
        lost = int(float(cols[6]))
        label = cols[9].strip('"').upper()
        if label == "PERSON" and lost == 0:
            frames[frame].append((xmin, ymin, xmax, ymax))
    return dict(frames)


def iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    inter = iw * ih
    area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union else 0.0


def match_boxes(
    truth: list[tuple[int, int, int, int]],
    predictions: list[Detection],
    threshold: float,
) -> tuple[int, int, int]:
    pairs: list[tuple[float, int, int]] = []
    for ti, gt in enumerate(truth):
        for pi, pred in enumerate(predictions):
            score = iou(gt, (pred.x1, pred.y1, pred.x2, pred.y2))
            if score >= threshold:
                pairs.append((score, ti, pi))

    used_t: set[int] = set()
    used_p: set[int] = set()
    for _, ti, pi in sorted(pairs, reverse=True):
        if ti in used_t or pi in used_p:
            continue
        used_t.add(ti)
        used_p.add(pi)

    tp = len(used_t)
    fp = len(predictions) - tp
    fn = len(truth) - tp
    return tp, fp, fn


def safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate one configured detector on EPFL Laboratory Camera 0."
    )
    parser.add_argument("--video", required=True)
    parser.add_argument("--ground-truth", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--detector", choices=["hog", "openvino"], required=True)
    parser.add_argument("--step-frames", type=int, default=25)
    parser.add_argument("--iou-threshold", type=float, default=0.5)
    args = parser.parse_args()

    os.environ["KAUSHALWATCH_PERSON_DETECTOR"] = args.detector
    detector = build_person_detector()
    annotations = parse_epfl_gt(Path(args.ground_truth))
    if not annotations:
        raise SystemExit("No EPFL annotations parsed")

    first_frame, last_frame = min(annotations), max(annotations)
    frames = [
        f for f in range(first_frame, last_frame + 1)
        if (f - first_frame) % args.step_frames == 0
    ]

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        raise SystemExit(f"Could not open video: {args.video}")

    rows: list[dict] = []
    total_tp = total_fp = total_fn = 0
    count_errors: list[int] = []

    try:
        for frame_no in frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
            ok, frame = cap.read()
            if not ok:
                rows.append({
                    "frame": frame_no,
                    "true_count": len(annotations.get(frame_no, [])),
                    "pred_count": "",
                    "tp": "", "fp": "", "fn": "",
                    "abs_count_error": "",
                    "status": "frame_unavailable",
                })
                continue

            truth = annotations.get(frame_no, [])
            predictions = detector.detect(frame)
            tp, fp, fn = match_boxes(truth, predictions, args.iou_threshold)
            total_tp += tp
            total_fp += fp
            total_fn += fn
            err = abs(len(predictions) - len(truth))
            count_errors.append(err)
            rows.append({
                "frame": frame_no,
                "true_count": len(truth),
                "pred_count": len(predictions),
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "abs_count_error": err,
                "status": "ok",
            })
    finally:
        cap.release()

    if not count_errors:
        raise SystemExit("No benchmark frames evaluated")

    precision = safe_div(total_tp, total_tp + total_fp)
    recall = safe_div(total_tp, total_tp + total_fn)
    f1 = safe_div(2 * precision * recall, precision + recall)

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "frame_metrics.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    report = {
        "dataset": "EPFL Laboratory six-person sequence, Camera 0 only",
        "detector": args.detector,
        "iou_threshold": args.iou_threshold,
        "sample_step_frames": args.step_frames,
        "evaluated_frames": len(count_errors),
        "true_positives": total_tp,
        "false_positives": total_fp,
        "false_negatives": total_fn,
        "person_precision": precision,
        "person_recall": recall,
        "person_f1": f1,
        "occupancy_mae": sum(count_errors) / len(count_errors),
        "max_abs_count_error": max(count_errors),
        "warning": (
            "Research benchmark only. Final SIH compliance-case accuracy must also be "
            "measured on the controlled training-centre demonstration."
        ),
    }
    (out / "count_metrics.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
