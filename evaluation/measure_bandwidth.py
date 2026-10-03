from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from app.services.offline_queue import bandwidth_measurement


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Measure KaushalWatch event/evidence transfer size against raw source video."
    )
    parser.add_argument("--video", required=True)
    parser.add_argument("--events", required=True, help="JSON file containing a list of edge events")
    parser.add_argument("--evidence-dir", default=None)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    video = Path(args.video)
    events_path = Path(args.events)
    if not video.exists():
        raise SystemExit(f"video not found: {video}")
    if not events_path.exists():
        raise SystemExit(f"events file not found: {events_path}")

    events = json.loads(events_path.read_text())
    if not isinstance(events, list):
        raise SystemExit("events JSON must contain a list")

    evidence_bytes = 0
    if args.evidence_dir:
        evidence_dir = Path(args.evidence_dir)
        if evidence_dir.exists():
            evidence_bytes = sum(
                p.stat().st_size for p in evidence_dir.rglob("*") if p.is_file()
            )

    report = bandwidth_measurement(
        raw_video_bytes=video.stat().st_size,
        events=events,
        evidence_bytes=evidence_bytes,
    )
    report["source_video"] = str(video)
    report["events_source"] = str(events_path)
    report["measurement_scope"] = (
        "File payload bytes only. Network protocol, TLS, retransmission and storage overhead are excluded."
    )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
