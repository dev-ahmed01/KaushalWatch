from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.services.video_pipeline import VideoCompliancePipeline


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Launch-gate check for the real KaushalWatch attendance pipeline. "
            "Fails if the primary detector is unavailable or the resulting stable "
            "occupancy falls outside the expected visual range."
        )
    )
    parser.add_argument("--video", required=True)
    parser.add_argument("--expected-min", type=int, required=True)
    parser.add_argument("--expected-max", type=int, required=True)
    parser.add_argument("--reported", type=int)
    parser.add_argument("--sample-every-seconds", type=float, default=0.2)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    )

    video = Path(args.video).expanduser().resolve()
    if not video.exists():
        raise SystemExit(f"Video not found: {video}")
    if args.expected_min > args.expected_max:
        raise SystemExit("--expected-min cannot exceed --expected-max")

    out = ROOT / "data" / "launch_gate"
    out.mkdir(parents=True, exist_ok=True)

    pipeline = VideoCompliancePipeline(
        out / "evidence",
        out / "evidence_index.json",
    )
    result = pipeline.run(
        video_path=video,
        reported_attendance=args.reported or args.expected_max,
        centre_id="LAUNCH-GATE",
        batch_id="REAL-FOOTAGE",
        camera_id="REAL-CAM",
        sample_every_seconds=args.sample_every_seconds,
    )

    payload = result.model_dump(mode="json")
    print(json.dumps(payload, indent=2))

    if not result.detector_authoritative:
        print(
            "\nFAIL: attendance detector is not authoritative: "
            f"{result.detector_message}",
            file=sys.stderr,
        )
        return 2

    if result.detector_failures:
        print(
            f"\nFAIL: detector raised {result.detector_failures} runtime error(s).",
            file=sys.stderr,
        )
        return 3

    if result.estimated_occupancy is None:
        print("\nFAIL: no authoritative occupancy was produced.", file=sys.stderr)
        return 4

    if not args.expected_min <= result.estimated_occupancy <= args.expected_max:
        print(
            "\nFAIL: stable occupancy "
            f"{result.estimated_occupancy} is outside visual sanity range "
            f"{args.expected_min}..{args.expected_max}.",
            file=sys.stderr,
        )
        return 5

    print(
        "\nPASS: primary detector returned a plausible non-zero real-footage "
        f"stable occupancy of {result.estimated_occupancy}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
