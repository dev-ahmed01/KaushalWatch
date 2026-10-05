from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import statistics
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.services.video_pipeline import VideoCompliancePipeline


def read_manual_counts(path: Path) -> list[dict]:
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    if not rows:
        raise ValueError(f"No annotation rows in {path}")

    parsed = []
    for row in rows:
        if "second" not in row or "true_count" not in row:
            raise ValueError("Manual CSV requires columns: second,true_count")
        second = float(row["second"])
        true_count = int(row["true_count"])
        if second < 0 or true_count < 0:
            raise ValueError("second and true_count must be >= 0")
        parsed.append({"second": second, "true_count": true_count})
    return parsed


def nearest_observation(observations, second: float):
    return min(observations, key=lambda obs: abs(float(obs.second) - second))


def metrics(rows: list[dict], field: str) -> dict:
    errors = [abs(row[field] - row["true_count"]) for row in rows]
    signed = [row[field] - row["true_count"] for row in rows]
    exact = sum(row[field] == row["true_count"] for row in rows)
    return {
        "mae": round(sum(errors) / len(errors), 4),
        "median_abs_error": round(float(statistics.median(errors)), 4),
        "max_abs_error": max(errors),
        "mean_bias": round(sum(signed) / len(signed), 4),
        "exact_count_rate": round(exact / len(rows), 4),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate attendance count fidelity against timestamped manual ground truth. "
            "Use this for clips where visible occupancy changes over time."
        )
    )
    parser.add_argument("--video", required=True)
    parser.add_argument("--manual-csv", required=True)
    parser.add_argument(
        "--sample-every-seconds",
        type=float,
        default=0.2,
    )
    parser.add_argument(
        "--max-time-delta",
        type=float,
        default=0.12,
        help="Maximum allowed distance between a manual timestamp and pipeline sample.",
    )
    parser.add_argument(
        "--out",
        default="evaluation/output/dynamic-attendance-report.json",
    )
    args = parser.parse_args()

    video = Path(args.video).expanduser().resolve()
    manual_path = Path(args.manual_csv).expanduser().resolve()
    if not video.exists():
        raise SystemExit(f"Video not found: {video}")
    if not manual_path.exists():
        raise SystemExit(f"Manual annotation CSV not found: {manual_path}")

    manual = read_manual_counts(manual_path)
    nominal_reported = int(round(statistics.median(row["true_count"] for row in manual)))

    with tempfile.TemporaryDirectory(prefix="kw-dynamic-attendance-") as temp:
        temp_root = Path(temp)
        pipeline = VideoCompliancePipeline(
            temp_root / "evidence",
            temp_root / "evidence-index.json",
        )
        result = pipeline.run(
            video_path=video,
            reported_attendance=nominal_reported,
            centre_id="HELDOUT-EVAL",
            batch_id="HELDOUT-EVAL",
            camera_id="HELDOUT-EVAL-CAM",
            sample_every_seconds=args.sample_every_seconds,
        )

    if not result.detector_authoritative:
        raise SystemExit(
            "Dynamic attendance evaluation requires an authoritative detector. "
            f"Current detector: {result.detector_message}"
        )
    if result.detector_failures:
        raise SystemExit(
            f"Detector failed during evaluation: {result.detector_failures} failure(s)"
        )

    comparisons = []
    for truth in manual:
        obs = nearest_observation(result.observations, truth["second"])
        delta = abs(float(obs.second) - truth["second"])
        if delta > args.max_time_delta:
            raise SystemExit(
                f"No pipeline sample within {args.max_time_delta:.3f}s of "
                f"manual timestamp {truth['second']:.3f}s; nearest={obs.second:.3f}s"
            )
        comparisons.append(
            {
                "manual_second": truth["second"],
                "sample_second": float(obs.second),
                "time_delta": round(delta, 4),
                "true_count": truth["true_count"],
                "raw_count": int(obs.raw_count),
                "tracker_count": int(obs.tracker_count),
                "confirmed_count": int(obs.confirmed_count),
                "registered_count": int(obs.registered_count),
                "smoothed_count": int(obs.smoothed_count),
                "camera_trust": float(obs.camera_trust),
            }
        )

    payload = {
        "video": str(video),
        "manual_csv": str(manual_path),
        "annotations": len(comparisons),
        "detector": {
            "backend": result.detector_backend,
            "mode": result.detector_mode,
            "authoritative": result.detector_authoritative,
            "message": result.detector_message,
            "failures": result.detector_failures,
        },
        "metrics": {
            "raw_count": metrics(comparisons, "raw_count"),
            "registered_count": metrics(comparisons, "registered_count"),
            "smoothed_count": metrics(comparisons, "smoothed_count"),
        },
        "comparisons": comparisons,
        "claim_boundary": (
            "Metrics apply only to the supplied manually annotated timestamps. "
            "The compliance decision itself compares camera occupancy with an external "
            "reported-attendance record and should not be scored by pretending a dynamic "
            "clip has one constant ground-truth count."
        ),
    }

    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(json.dumps(payload, indent=2))
    print(f"\nFull report: {out}")


if __name__ == "__main__":
    main()
