from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
import sys
import time
from pathlib import Path
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.services.offline_queue import EdgeEventQueue, json_payload_bytes
from app.services.edge_ingest import _safe_details
from app.services.video_pipeline import VideoCompliancePipeline


DEFAULT_QUEUE = ROOT / "data" / "edge" / "queue.json"
DEFAULT_EVIDENCE = ROOT / "data" / "edge" / "evidence"
DEFAULT_INDEX = ROOT / "data" / "edge" / "evidence-index.json"
DEFAULT_SCHEDULE_STATE = ROOT / "data" / "edge" / "schedule-state.json"


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
        "details": _safe_details(case.details),
        "created_at": case.created_at,
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


def analysis_to_edge_payload(result, *, centre_id: str, batch_id: str) -> dict:
    # A camera-insufficient run is not compliant, even if the person detector
    # itself is authoritative or no attendance-discrepancy case exists.
    trustworthy = (
        result.detector_authoritative
        and result.detector_failures == 0
        and result.trusted_sample_ratio >= 0.5
    )
    if not trustworthy or result.decision in {"camera_evidence_insufficient", "detector_unavailable"}:
        outcome = "blocked"
        summary = "Attendance inference blocked: camera or detector evidence is insufficient."
    elif result.case:
        outcome = "attention"
        summary = result.case.summary
    elif result.decision == "compliant":
        outcome = "compliant"
        summary = "Attendance matched the reported record."
    else:
        outcome = "blocked"
        summary = "Attendance inference could not establish a compliant result."

    return {
        "centre_id": centre_id,
        "batch_id": batch_id,
        "analysis_type": "attendance",
        "outcome": outcome,
        "summary": summary,
        "details": {
            "reported_attendance": result.reported_attendance,
            "estimated_occupancy": result.estimated_occupancy,
            "discrepancy_pct": result.discrepancy_pct,
            "decision": result.decision,
            "detector_backend": result.detector_backend,
            "detector_authoritative": result.detector_authoritative,
            "detector_failures": result.detector_failures,
            "trusted_sample_ratio": result.trusted_sample_ratio,
        },
        "privacy": {
            "raw_video_included": False,
            "individual_identification": False,
        },
    }


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

    summary_event = queue.enqueue(
        "analysis_summary",
        analysis_to_edge_payload(
            result,
            centre_id=args.centre_id,
            batch_id=args.batch_id,
        ),
    )

    output = {
        "estimated_occupancy": result.estimated_occupancy,
        "reported_attendance": result.reported_attendance,
        "discrepancy_pct": result.discrepancy_pct,
        "case_created": result.case is not None,
        "raw_video_uploaded": False,
        "analysis_event_id": summary_event["event_id"],
    }

    if result.case:
        event = queue.enqueue(
            "compliance_case",
            case_to_edge_payload(result.case),
        )
        output["queued_case_event_id"] = event["event_id"]
        output["queued_case_event_bytes"] = json_payload_bytes(event)

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
    # Keep device credentials out of CLI arguments and stdout; use an
    # environment-provided opaque secret for externally exposed endpoints.
    token = os.getenv("KAUSHALWATCH_EDGE_SYNC_TOKEN", "").strip()
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "KaushalWatch-Edge/1.0",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(
        args.url.rstrip("/") + "/api/edge/sync",
        data=body,
        headers=headers,
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

    accepted = payload.get("accepted_event_ids", []) if isinstance(payload, dict) else None
    sent = {event.get("event_id") for event in events}
    if (not isinstance(accepted, list) or any(
            not isinstance(item, str) or item not in sent for item in accepted)):
        print(json.dumps({"synced": 0, "remaining": len(events),
                          "error": "Invalid server event acknowledgement"}, indent=2))
        return 2
    # The server may reject unsafe/corrupt events. Rejected items remain on
    # disk for explicit operator repair; never silently discard them.
    # A malicious/incorrect response also cannot acknowledge unrelated events
    # appended by a second local producer after this request started.
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


def fetch_settings(api_url: str, centre_id: str, timeout: float = 15.0) -> dict:
    request = Request(
        api_url.rstrip("/") + f"/api/centres/{centre_id}/settings",
        headers={"User-Agent": "KaushalWatch-Edge/1.0"},
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _read_schedule_state(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_schedule_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2))


def scheduled_window_key(settings: dict, now: datetime) -> str | None:
    """Return a unique due-window key, or None when automatic analysis is not due."""
    if not settings.get("automatic_analysis", False):
        return None
    if settings.get("frequency") == "manual":
        return None

    current_minutes = now.hour * 60 + now.minute
    for raw in settings.get("monitoring_windows") or []:
        try:
            start_raw, end_raw = str(raw).split("-", 1)
            start_h, start_m = [int(value) for value in start_raw.strip().split(":", 1)]
            end_h, end_m = [int(value) for value in end_raw.strip().split(":", 1)]
        except (ValueError, TypeError):
            continue
        start = start_h * 60 + start_m
        end = end_h * 60 + end_m
        if start <= current_minutes < end:
            return f"{now.date().isoformat()}|{start_h:02d}:{start_m:02d}-{end_h:02d}:{end_m:02d}"
    return None


def watch(args) -> int:
    """Run attendance automatically once per configured monitoring window.

    The edge process must be attached to a local capture/buffer file. Raw video
    remains local; only compact analysis summaries and exception telemetry sync.
    """
    state_path = Path(args.state_file)

    while True:
        try:
            settings = fetch_settings(args.api_url, args.centre_id, timeout=args.timeout)
        except (URLError, HTTPError, TimeoutError, json.JSONDecodeError) as exc:
            print(json.dumps({"scheduler": "offline", "error": str(exc)}, indent=2))
            if args.once:
                return 2
            time.sleep(args.poll_seconds)
            continue

        now = datetime.now().astimezone()
        key = scheduled_window_key(settings, now)
        state = _read_schedule_state(state_path)

        if key and state.get("last_run_key") != key:
            print(json.dumps({
                "scheduler": "triggered",
                "centre_id": args.centre_id,
                "window_key": key,
                "source": str(Path(args.video).expanduser()),
            }, indent=2))
            rc = analyze(args)
            if rc == 0:
                state["last_run_key"] = key
                state["last_run_at"] = now.isoformat()
                _write_schedule_state(state_path, state)
                if args.sync:
                    sync_args = argparse.Namespace(
                        queue=args.queue,
                        url=args.api_url,
                        timeout=args.timeout,
                    )
                    sync(sync_args)
        else:
            print(json.dumps({
                "scheduler": "waiting",
                "centre_id": args.centre_id,
                "automatic_analysis": bool(settings.get("automatic_analysis")),
                "frequency": settings.get("frequency"),
                "window_key": key,
                "already_ran_window": bool(key and state.get("last_run_key") == key),
                "checked_at": now.isoformat(),
            }, indent=2))

        if args.once:
            return 0
        time.sleep(args.poll_seconds)


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

    watch_p = sub.add_parser(
        "watch",
        help="Automatically run once per configured monitoring window on a connected local source",
    )
    watch_p.add_argument("--video", required=True, help="Local camera buffer/recording path used by the edge runtime")
    watch_p.add_argument("--reported-attendance", type=int, required=True)
    watch_p.add_argument("--centre-id", default="DEMO-KA-104")
    watch_p.add_argument("--batch-id", default="ELEC-DEMO-01")
    watch_p.add_argument("--camera-id", default="LAB-CAM-01")
    watch_p.add_argument("--evidence-dir", default=str(DEFAULT_EVIDENCE))
    watch_p.add_argument("--evidence-index", default=str(DEFAULT_INDEX))
    watch_p.add_argument("--state-file", default=str(DEFAULT_SCHEDULE_STATE))
    watch_p.add_argument("--api-url", default=os.getenv("KAUSHALWATCH_API_URL", "http://127.0.0.1:8000"))
    watch_p.add_argument("--timeout", type=float, default=15.0)
    watch_p.add_argument("--poll-seconds", type=int, default=60)
    watch_p.add_argument("--sync", action="store_true", help="Sync compact telemetry after each scheduled run")
    watch_p.add_argument("--once", action="store_true", help="Check the schedule once and exit")
    watch_p.set_defaults(func=watch)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
