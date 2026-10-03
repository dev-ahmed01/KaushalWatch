from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

import cv2

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from app.services.person_detector import build_person_detector


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark a configured person detector on annotated video timestamps."
    )
    parser.add_argument("--video", required=True)
    parser.add_argument("--ground-truth", required=True, help="CSV: second,true_count")
    parser.add_argument("--out-dir", default="evaluation/output/person-count")
    parser.add_argument("--detector", choices=["hog", "openvino"], default=None)
    args = parser.parse_args()

    if args.detector:
        os.environ["KAUSHALWATCH_PERSON_DETECTOR"] = args.detector

    detector = build_person_detector()
    truth_rows = list(csv.DictReader(Path(args.ground_truth).open()))
    if not truth_rows:
        raise SystemExit("Ground-truth CSV is empty")

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        raise SystemExit(f"Could not open video: {args.video}")

    output_rows = []
    errors = []
    try:
        for row in truth_rows:
            second = float(row["second"])
            true_count = int(row["true_count"])
            cap.set(cv2.CAP_PROP_POS_MSEC, second * 1000.0)
            ok, frame = cap.read()
            if not ok:
                output_rows.append({
                    "second": second,
                    "true_count": true_count,
                    "pred_count": "",
                    "abs_error": "",
                    "status": "frame_unavailable",
                })
                continue
            pred_count = len(detector.detect(frame))
            err = abs(pred_count - true_count)
            errors.append(err)
            output_rows.append({
                "second": second,
                "true_count": true_count,
                "pred_count": pred_count,
                "abs_error": err,
                "status": "ok",
            })
    finally:
        cap.release()

    if not errors:
        raise SystemExit("No benchmark frames could be evaluated")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "count_predictions.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=output_rows[0].keys())
        writer.writeheader()
        writer.writerows(output_rows)

    report = {
        "detector": os.getenv("KAUSHALWATCH_PERSON_DETECTOR", "hog"),
        "video": str(Path(args.video)),
        "ground_truth": str(Path(args.ground_truth)),
        "evaluated_samples": len(errors),
        "occupancy_mae": sum(errors) / len(errors),
        "max_abs_error": max(errors),
        "warning": "Metrics are valid only for the supplied timestamp/count annotations.",
    }
    (out_dir / "count_metrics.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
