from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.config import demo_scenario_path
from app.services.demo_assets import load_demo_manifest_and_cache
from app.services.infrastructure_pipeline import InfrastructureCompliancePipeline
from app.services.offline_queue import bandwidth_measurement
from app.services.video_pipeline import VideoCompliancePipeline


def case_event(case) -> dict:
    if case is None:
        return {"event_type": "no_case", "payload": {}}
    return {
        "event_type": case.case_type,
        "payload": {
            "case_id": case.case_id,
            "centre_id": case.centre_id,
            "batch_id": case.batch_id,
            "severity": case.severity,
            "status": case.status.value,
            "discrepancy_pct": case.discrepancy_pct,
            "persistence_ratio": case.persistence_ratio,
            "details": case.details,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the exact final video through KaushalWatch core demo paths."
    )
    parser.add_argument(
        "--video",
        default=os.getenv("KAUSHALWATCH_DEMO_VIDEO"),
        required=False,
    )
    parser.add_argument("--out", default="evaluation/output/final-demo/rehearsal_report.json")
    args = parser.parse_args()

    if not args.video:
        raise SystemExit("Provide --video or KAUSHALWATCH_DEMO_VIDEO")

    video = Path(args.video).expanduser().resolve()
    if not video.exists():
        raise SystemExit(f"Video not found: {video}")

    scenario_path = demo_scenario_path()
    if not scenario_path.exists():
        raise SystemExit(f"Scenario not found: {scenario_path}")
    scenario = json.loads(scenario_path.read_text())
    manifest, detection_rows = load_demo_manifest_and_cache()

    centre_id = scenario["centre_id"]
    batch_id = scenario["batch_id"]
    camera_id = scenario["camera_id"]
    reported = int(scenario["reported_attendance"])

    roi_cfg = scenario.get("operability_roi") or {}
    roi = None
    item_id = None
    if all(k in roi_cfg for k in ("x1", "y1", "x2", "y2")):
        roi = tuple(int(roi_cfg[k]) for k in ("x1", "y1", "x2", "y2"))
        item_id = roi_cfg.get("item_id")

    with tempfile.TemporaryDirectory(prefix="kaushalwatch-rehearsal-") as temp:
        temp_root = Path(temp)
        evidence_dir = temp_root / "evidence"
        evidence_index = temp_root / "evidence-index.json"

        attendance_pipeline = VideoCompliancePipeline(evidence_dir, evidence_index)
        infrastructure_pipeline = InfrastructureCompliancePipeline(
            evidence_dir,
            evidence_index,
            privacy_detector=attendance_pipeline.detector,
        )

        attendance = attendance_pipeline.run(
            video_path=video,
            reported_attendance=reported,
            centre_id=centre_id,
            batch_id=batch_id,
            camera_id=camera_id,
        )
        infrastructure = infrastructure_pipeline.run(
            video_path=video,
            manifest=manifest,
            detection_rows=detection_rows,
            centre_id=centre_id,
            batch_id=batch_id,
            camera_id=camera_id,
            operability_item_id=item_id if roi else None,
            operability_roi=roi,
        )

        events = [case_event(attendance.case), case_event(infrastructure)]
        evidence_files = list(evidence_dir.glob("*"))
        evidence_bytes = sum(p.stat().st_size for p in evidence_files if p.is_file())
        bandwidth = bandwidth_measurement(video.stat().st_size, events, evidence_bytes)

        report = {
            "scenario_id": scenario.get("scenario_id"),
            "video": str(video),
            "detector_backend": os.getenv("KAUSHALWATCH_PERSON_DETECTOR", "hog"),
            "attendance": attendance.model_dump(mode="json"),
            "infrastructure_case": (
                infrastructure.model_dump(mode="json") if infrastructure else None
            ),
            "bandwidth": bandwidth,
            "stage_checks": {
                "attendance_case_created": attendance.case is not None,
                "infrastructure_case_created": infrastructure is not None,
                "evidence_files_created": len(evidence_files),
                "operability_state": (
                    infrastructure.details.get("apparent_operability", {}).get("state")
                    if infrastructure else None
                ),
            },
            "claim_boundary": (
                "Rehearsal output validates the configured pipeline on this video. "
                "Accuracy claims still require independent ground-truth annotations."
            ),
        }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
