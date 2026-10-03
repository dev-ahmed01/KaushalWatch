from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.services.offline_queue import EdgeEventQueue, json_payload_bytes
from app.services.video_pipeline import VideoCompliancePipeline


DEFAULT_QUEUE = ROOT / "data" / "edge" / "queue.json"
DEFAULT_EVIDENCE = ROOT / "data" / "edge" / "evidence"
DEFAULT_INDEX = ROOT / "data" / "edge" / "evidence-index.json"


def case_to_edge_payload(case) -> dict:
    """Create minimal central telemetry without local file paths or raw images."""
    payload = {
        "case_id": case.case_id,
        "centre_id": case.centre_id,
        "batch_id": case.batch_id,
        "case_type": case.case_type,
        "severity": case.severity,
        "summary": case.summary,
        "status": case.status.value,
        "reported_attendance": case.reported_attendance,
        "visual_occupancy": case.visual_occupancy,
        "discrepancy_pct": case.discrepancy_pct,
        "persistence_ratio": case.persistence_ratio,
        "details": case.details,
        "evidence_integrity": [
            {
                "evidence_id": evidence.evidence_id,
                "sha256": evidence.sha256,
                "perceptual_hash": evidence.perceptual_hash,
                "possible_duplicate": evidence.duplicate_of is not None,
                "duplicate_of": evidence.duplicate_of,
            }
            for evidence in case.evidence
        ],
        "privacy": {
            "individual_identification": False,
            "face_embeddings": False,
            "raw_video_included": False,
        },
    }
    return payload


def analyze(args) -> int:
    video = Path(args.video).expanduser().resolve()
    if not video.exists():
        raise SystemExit(f"Video not found: {video}")

    queue = EdgeEventQueue(Path(args.queue))
    pipeline = VideoCompliancePipeline(
        Path(args.evidence_dir),
        Path(args.evidence_index),
    )
    result = pipeline.run(
        video_path=video,
        reported_attendance=args.reported_attendance,
        centre_id=args.centre_id,
        batch_id=args.batch_id,
        camera_id=args.camera_id,
    )

    output = {
        "estimated_occupancy": result.estimated_occupancy,
        "reported_attendance": result.reported_attendance,
        "discrepancy_pct": result.discrepancy_pct,
        "case_created": result.case is not None,
        "raw_video_uploaded": False,
    }

    if result.case:
        event = queue.enqueue(
            "compliance_case",
            case_to_edge_payload(result.case),
        )
        output["queued_event_id"] = event["event_id"]
        output["queued_event_bytes"] = json_payload_bytes(event)

    output["queue_depth"] = len(queue.pending())
    print(json.dumps(output, indent=2))
    return 0


def sync(args) -> int:
    queue = EdgeEventQueue(Path(args.queue))
    events = queue.pending()
    if not events:
        print(json.dumps({"synced": 0, "remaining": 0, "message": "queue empty"}, indent=2))
        return 0

    body = json.dumps({"events": events}, separators=(",", ":")).encode("utf-8")
    request = Request(
        args.url.rstrip("/") + "/api/edge/sync",
        data=body,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "KaushalWatch-Edge/1.0",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=args.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (URLError, HTTPError, TimeoutError) as exc:
        print(json.dumps({
            "synced": 0,
            "remaining": len(events),
            "offline": True,
            "error": str(exc),
            "raw_video_uploaded": False,
        }, indent=2))
        return 2

    accepted = payload.get("accepted_event_ids", [])
    removed = queue.acknowledge(accepted)
    print(json.dumps({
        "synced": removed,
        "remaining": len(queue.pending()),
        "server": payload,
        "raw_video_uploaded": False,
    }, indent=2))
    return 0


def status(args) -> int:
    queue = EdgeEventQueue(Path(args.queue))
    events = queue.pending()
    print(json.dumps({
        "queue_depth": len(events),
        "queued_payload_bytes": json_payload_bytes(events),
        "raw_video_queued": False,
        "events": [
            {
                "event_id": e.get("event_id"),
                "event_type": e.get("event_type"),
                "created_at": e.get("created_at"),
            }
            for e in events
        ],
    }, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="KaushalWatch edge/offline prototype agent")
    parser.add_argument("--queue", default=str(DEFAULT_QUEUE))
    sub = parser.add_subparsers(dest="command", required=True)

    analyze_p = sub.add_parser("analyze", help="Process local video and queue only compliance telemetry")
    analyze_p.add_argument("--video", required=True)
    analyze_p.add_argument("--reported-attendance", type=int, required=True)
    analyze_p.add_argument("--centre-id", default="DEMO-KA-104")
    analyze_p.add_argument("--batch-id", default="ELEC-DEMO-01")
    analyze_p.add_argument("--camera-id", default="LAB-CAM-01")
    analyze_p.add_argument("--evidence-dir", default=str(DEFAULT_EVIDENCE))
    analyze_p.add_argument("--evidence-index", default=str(DEFAULT_INDEX))
    analyze_p.set_defaults(func=analyze)

    sync_p = sub.add_parser("sync", help="Sync queued telemetry after connectivity returns")
    sync_p.add_argument("--url", default=os.getenv("KAUSHALWATCH_API_URL", "http://127.0.0.1:8000"))
    sync_p.add_argument("--timeout", type=float, default=15.0)
    sync_p.set_defaults(func=sync)

    status_p = sub.add_parser("status", help="Show local offline queue state")
    status_p.set_defaults(func=status)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
