from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import statistics
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.services.person_detector import OpenVinoPersonDetector, _resolve_openvino_xml
from app.services.video_pipeline import VideoCompliancePipeline


def parse_thresholds(raw: str) -> list[float]:
    values = []
    for part in raw.split(","):
        value = float(part.strip())
        if not 0 < value < 1:
            raise ValueError("confidence thresholds must be between 0 and 1")
        values.append(value)
    return sorted(set(values))


def summarize(result, true_count: int, *, confidence: float, tiled: bool) -> dict:
    trusted = [row for row in result.observations if row.camera_trust >= 50]
    raw_counts = [row.raw_count for row in trusted]
    registered_counts = [
        row.registered_count
        for row in trusted
        if row.second >= 2.0
    ]
    raw_mae = (
        sum(abs(value - true_count) for value in raw_counts) / len(raw_counts)
        if raw_counts else None
    )
    registered_mae = (
        sum(abs(value - true_count) for value in registered_counts)
        / len(registered_counts)
        if registered_counts else None
    )
    exact_raw_fraction = (
        sum(value == true_count for value in raw_counts) / len(raw_counts)
        if raw_counts else 0.0
    )
    exact_registered_fraction = (
        sum(value == true_count for value in registered_counts) / len(registered_counts)
        if registered_counts else 0.0
    )
    raw_mode = Counter(raw_counts).most_common(1)[0][0] if raw_counts else None
    registered_mode = (
        Counter(registered_counts).most_common(1)[0][0]
        if registered_counts else None
    )
    estimated = result.estimated_occupancy
    stable_error = abs(estimated - true_count) if estimated is not None else 999

    return {
        "confidence": confidence,
        "tiled": tiled,
        "detector_message": result.detector_message,
        "estimated_occupancy": estimated,
        "stable_occupancy_abs_error": stable_error,
        "decision": result.decision,
        "discrepancy_pct": result.discrepancy_pct,
        "mismatch_persistence_ratio": result.mismatch_persistence_ratio,
        "trusted_sample_ratio": result.trusted_sample_ratio,
        "frames_sampled": result.frames_sampled,
        "detector_failures": result.detector_failures,
        "raw_count_mode": raw_mode,
        "raw_count_median": statistics.median(raw_counts) if raw_counts else None,
        "raw_count_min": min(raw_counts) if raw_counts else None,
        "raw_count_max": max(raw_counts) if raw_counts else None,
        "raw_count_mae": round(raw_mae, 4) if raw_mae is not None else None,
        "exact_raw_fraction": round(exact_raw_fraction, 4),
        "registered_count_mode_after_2s": registered_mode,
        "registered_count_mae_after_2s": (
            round(registered_mae, 4) if registered_mae is not None else None
        ),
        "exact_registered_fraction_after_2s": round(
            exact_registered_fraction,
            4,
        ),
    }


def rank_key(row: dict) -> tuple:
    # First require the final stable occupancy to match ground truth. Then prefer
    # consistent registered occupancy, raw-count accuracy, fewer over-counts,
    # and finally the higher confidence threshold as the more conservative tie-break.
    return (
        row["stable_occupancy_abs_error"],
        row["registered_count_mae_after_2s"]
        if row["registered_count_mae_after_2s"] is not None else 999,
        row["raw_count_mae"] if row["raw_count_mae"] is not None else 999,
        -row["exact_registered_fraction_after_2s"],
        -row["exact_raw_fraction"],
        -row["confidence"],
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Compare OpenVINO confidence and tiled-inference variants on one "
            "manually counted attendance clip. This is a calibration aid, not "
            "a substitute for held-out evaluation."
        )
    )
    parser.add_argument("--video", required=True)
    parser.add_argument("--true-count", required=True, type=int)
    parser.add_argument(
        "--thresholds",
        default="0.25,0.30,0.35,0.40,0.45",
        help="Comma-separated OpenVINO confidence thresholds.",
    )
    parser.add_argument(
        "--variants",
        default="full,tiled",
        help="Comma-separated variants: full,tiled",
    )
    parser.add_argument(
        "--sample-every-seconds",
        default=0.2,
        type=float,
    )
    parser.add_argument(
        "--out",
        default="evaluation/output/attendance-calibration.json",
    )
    args = parser.parse_args()

    video = Path(args.video).expanduser().resolve()
    if not video.exists():
        raise SystemExit(f"Video not found: {video}")
    if args.true_count < 0:
        raise SystemExit("--true-count must be >= 0")

    thresholds = parse_thresholds(args.thresholds)
    variants = [item.strip().lower() for item in args.variants.split(",") if item.strip()]
    unknown = sorted(set(variants) - {"full", "tiled"})
    if unknown:
        raise SystemExit(f"Unknown variants: {unknown}")

    model_xml = _resolve_openvino_xml()
    if not model_xml.exists():
        raise SystemExit(
            f"OpenVINO model not found: {model_xml}. "
            "Run scripts/prepare_demo_vision.py --install first."
        )

    rows: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="kw-attendance-calibration-") as temp:
        temp_root = Path(temp)
        for variant in variants:
            tiled = variant == "tiled"
            for confidence in thresholds:
                detector = OpenVinoPersonDetector(
                    model_xml,
                    confidence=confidence,
                    tiled=tiled,
                )
                pipeline = VideoCompliancePipeline(
                    temp_root / f"evidence-{variant}-{confidence:.2f}",
                    temp_root / f"index-{variant}-{confidence:.2f}.json",
                    detector=detector,
                )
                result = pipeline.run(
                    video_path=video,
                    reported_attendance=args.true_count,
                    centre_id="CALIBRATION",
                    batch_id="CALIBRATION",
                    camera_id="CALIBRATION-CAM",
                    sample_every_seconds=args.sample_every_seconds,
                )
                row = summarize(
                    result,
                    args.true_count,
                    confidence=confidence,
                    tiled=tiled,
                )
                rows.append(row)
                print(
                    f"{variant:5s} conf={confidence:.2f} "
                    f"stable={row['estimated_occupancy']} "
                    f"reg_mae={row['registered_count_mae_after_2s']} "
                    f"raw_mae={row['raw_count_mae']} "
                    f"decision={row['decision']}"
                )

    ranked = sorted(rows, key=rank_key)
    payload = {
        "video": str(video),
        "manual_true_count": args.true_count,
        "results": rows,
        "recommended_candidate": ranked[0] if ranked else None,
        "selection_rule": (
            "Stable occupancy error first; then registered-count MAE, raw-count "
            "MAE, exact-count fractions, and higher confidence as a conservative "
            "tie-break. Validate the selected candidate on held-out footage before "
            "changing benchmark claims."
        ),
        "claim_boundary": (
            "This calibration is specific to the supplied manually counted clip. "
            "It does not establish general accuracy."
        ),
    }

    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print("\nRecommended candidate:")
    print(json.dumps(payload["recommended_candidate"], indent=2))
    print(f"\nFull report: {out}")


if __name__ == "__main__":
    main()
