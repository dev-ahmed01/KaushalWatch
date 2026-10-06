from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BACKEND))

from app.models import ComplianceCase, CaseStatus
from app.services.analysis_history import AnalysisHistoryStore
from app.services.case_store import CaseStore
from app.services.evidence import persist_evidence
from scripts.reset_demo_state import reset_demo_state

DEFAULT_DATA = ROOT / "data"
DEMO_TIMEZONE = timezone(timedelta(hours=5, minutes=30))


def _simulated_evidence_frame() -> np.ndarray:
    frame = np.full((720, 1280, 3), 242, dtype=np.uint8)
    cv2.rectangle(frame, (48, 48), (1232, 672), (210, 216, 224), 2)
    cv2.putText(
        frame,
        "SIMULATED EVIDENCE - NO REAL PERSON",
        (82, 112),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (45, 55, 72),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        frame,
        "Anonymous position boxes for prototype integrity demonstration",
        (82, 158),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.62,
        (90, 101, 119),
        1,
        cv2.LINE_AA,
    )
    boxes = [(180, 250, 330, 560), (500, 230, 650, 560), (820, 265, 970, 560)]
    for index, (x1, y1, x2, y2) in enumerate(boxes, start=1):
        cv2.rectangle(frame, (x1, y1), (x2, y2), (82, 96, 115), 2)
        cv2.putText(
            frame,
            f"POSITION {index}",
            (x1, y1 - 14),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (82, 96, 115),
            1,
            cv2.LINE_AA,
        )
    cv2.putText(
        frame,
        "Track position, not identity",
        (82, 630),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (45, 55, 72),
        2,
        cv2.LINE_AA,
    )
    return frame


def _demo_activity_buckets(now: datetime, profile: str) -> list[dict]:
    local_now = now.astimezone(DEMO_TIMEZONE)
    day = (local_now - timedelta(days=1)).date()

    profiles = {
        "review": [
            ("09:00", "09:45", 0.48, 0.93, 2),
            ("09:45", "10:30", 0.72, 0.95, 3),
            ("10:45", "12:00", 0.91, 0.96, 4),
            ("12:00", "13:00", 0.62, 0.94, 3),
            ("13:00", "14:00", 0.41, 0.92, 2),
            ("14:00", "14:45", 0.18, 0.95, 1),
            ("14:45", "16:00", 0.66, 0.94, 3),
        ],
        "steady": [
            ("09:00", "10:00", 0.58, 0.96, 2),
            ("10:00", "11:00", 0.75, 0.96, 3),
            ("11:00", "12:00", 0.82, 0.97, 3),
            ("13:00", "14:00", 0.61, 0.95, 2),
            ("14:00", "15:00", 0.69, 0.96, 3),
            ("15:00", "16:00", 0.64, 0.96, 2),
        ],
        "blocked": [
            ("09:00", "10:00", 0.0, 0.21, 0),
            ("10:00", "11:00", 0.0, 0.18, 0),
            ("14:00", "15:00", 0.0, 0.24, 0),
        ],
    }

    rows = []
    for start_text, end_text, score, trust, cells in profiles[profile]:
        start_hour, start_minute = (int(part) for part in start_text.split(":"))
        end_hour, end_minute = (int(part) for part in end_text.split(":"))
        start = datetime(
            day.year, day.month, day.day, start_hour, start_minute,
            tzinfo=DEMO_TIMEZONE,
        )
        end = datetime(
            day.year, day.month, day.day, end_hour, end_minute,
            tzinfo=DEMO_TIMEZONE,
        )
        rows.append({
            "start_at": start.isoformat(),
            "end_at": end.isoformat(),
            "activity_score": score,
            "trusted_frame_ratio": trust,
            "active_work_cells": cells,
            "simulated": True,
            "source": "simulated_scheduled_practical_analysis",
        })
    return rows


def _append_history(
    history: AnalysisHistoryStore,
    *,
    centre_id: str,
    batch_id: str,
    analysis_type: str,
    outcome: str,
    summary: str,
    details: dict | None = None,
) -> None:
    history.append(
        centre_id=centre_id,
        batch_id=batch_id,
        analysis_type=analysis_type,
        outcome=outcome,
        summary=summary,
        details={"simulated": True, **(details or {})},
    )


def prepare_demo_state(data_dir: Path) -> dict:
    data_dir = data_dir.resolve()
    reset_result = reset_demo_state(data_dir)

    store = CaseStore(data_dir / "cases.json")
    history = AnalysisHistoryStore(data_dir / "analysis_history.json")
    evidence_dir = data_dir / "evidence"
    evidence_index = data_dir / "evidence_index.json"

    frame = _simulated_evidence_frame()
    evidence_primary = persist_evidence(
        frame,
        evidence_dir,
        evidence_index,
        "SIM-EV-KA104-01",
        {
            "simulated": True,
            "purpose": "prototype_integrity_demo",
            "privacy": "anonymous_position_boxes_only",
        },
    )
    evidence_duplicate = persist_evidence(
        frame.copy(),
        evidence_dir,
        evidence_index,
        "SIM-EV-KA104-DUP",
        {
            "simulated": True,
            "purpose": "prototype_duplicate_detection_demo",
            "privacy": "anonymous_position_boxes_only",
        },
    )

    now = datetime.now(timezone.utc)
    cases = [
        ComplianceCase(
            case_id="SIM-KA-104-ATT",
            centre_id="DEMO-KA-104",
            batch_id="ELEC-2026-08",
            case_type="attendance_discrepancy",
            status=CaseStatus.open,
            severity="medium",
            summary="Reported 28 trainees; sustained simulated visual evidence showed 19.",
            reported_attendance=28,
            visual_occupancy=19,
            details={
                "simulated": True,
                "temporal_proof": "Persisted across 3 simulated analysis periods",
            },
            evidence=[evidence_primary],
            created_at=(now - timedelta(hours=2)).isoformat(),
        ),
        ComplianceCase(
            case_id="SIM-KA-207-CAM",
            centre_id="DEMO-KA-207",
            batch_id="ELEC-2026-09",
            case_type="camera_integrity",
            status=CaseStatus.open,
            severity="medium",
            summary="Camera view became obstructed; dependent conclusions are suspended.",
            details={
                "simulated": True,
                "camera_state": "untrusted",
                "decision": "suspend_dependent_conclusions",
            },
            created_at=(now - timedelta(hours=1)).isoformat(),
        ),
        ComplianceCase(
            case_id="SIM-KA-303-INF",
            centre_id="DEMO-KA-303",
            batch_id="ELEC-2026-06",
            case_type="infrastructure_compliance",
            status=CaseStatus.open,
            severity="high",
            summary="Required training panels remained below the simulated reported quantity.",
            details={
                "simulated": True,
                "reported_quantity": 12,
                "observed_quantity": 9,
                "temporal_proof": "Observed in 3 simulated review periods",
            },
            created_at=(now - timedelta(days=4)).isoformat(),
        ),
        ComplianceCase(
            case_id="SIM-KA-104-DUP",
            centre_id="DEMO-KA-104",
            batch_id="ELEC-2026-08",
            case_type="evidence_integrity",
            status=CaseStatus.resolved,
            severity="low",
            summary="Simulated duplicate-evidence test record.",
            details={"simulated": True, "test_only": True},
            evidence=[evidence_duplicate],
            created_at=(now - timedelta(hours=3)).isoformat(),
        ),
    ]
    for case in cases:
        store.save(case)

    # Bengaluru — review needed.
    _append_history(history, centre_id="DEMO-KA-104", batch_id="ELEC-2026-08", analysis_type="attendance", outcome="attention", summary="Simulated attendance gap persisted across trusted periods.", details={"reported": 28, "observed": 19})
    _append_history(
        history,
        centre_id="DEMO-KA-104",
        batch_id="ELEC-2026-08",
        analysis_type="practical_work",
        outcome="compliant",
        summary="Simulated practical activity evidence aligned.",
        details={
            "activity_fraction": 0.62,
            "active_work_cells": 4,
            "peak_stable_workers": 6,
            "trusted_frame_ratio": 0.94,
            "activity_buckets": _demo_activity_buckets(now, "review"),
        },
    )
    _append_history(history, centre_id="DEMO-KA-104", batch_id="ELEC-2026-08", analysis_type="infrastructure", outcome="compliant", summary="Simulated infrastructure presence aligned with the manifest.")

    # Mysuru — verified.
    for analysis_type in ("attendance", "practical_work", "infrastructure"):
        details = (
            {
                "activity_fraction": 0.68,
                "active_work_cells": 3,
                "peak_stable_workers": 5,
                "trusted_frame_ratio": 0.96,
                "activity_buckets": _demo_activity_buckets(now, "steady"),
            }
            if analysis_type == "practical_work"
            else None
        )
        _append_history(
            history,
            centre_id="DEMO-KA-112",
            batch_id="ELEC-2026-07",
            analysis_type=analysis_type,
            outcome="compliant",
            summary=f"Simulated {analysis_type.replace('_', ' ')} evidence aligned.",
            details=details,
        )

    # Tumakuru — camera trust issue; dependent conclusions are blocked.
    for analysis_type in ("attendance", "practical_work", "infrastructure"):
        details = {"camera_trust": "untrusted"}
        if analysis_type == "practical_work":
            details.update({
                "activity_fraction": 0.0,
                "active_work_cells": 0,
                "peak_stable_workers": 0,
                "trusted_frame_ratio": 0.21,
                "activity_buckets": _demo_activity_buckets(now, "blocked"),
            })
        _append_history(
            history,
            centre_id="DEMO-KA-207",
            batch_id="ELEC-2026-09",
            analysis_type=analysis_type,
            outcome="blocked",
            summary="Simulated camera obstruction suspended this conclusion.",
            details=details,
        )

    # Hubballi — infrastructure review and aged escalation.
    _append_history(history, centre_id="DEMO-KA-303", batch_id="ELEC-2026-06", analysis_type="attendance", outcome="compliant", summary="Simulated attendance evidence aligned.")
    _append_history(
        history,
        centre_id="DEMO-KA-303",
        batch_id="ELEC-2026-06",
        analysis_type="practical_work",
        outcome="compliant",
        summary="Simulated practical activity evidence aligned.",
        details={
            "activity_fraction": 0.65,
            "active_work_cells": 3,
            "peak_stable_workers": 5,
            "trusted_frame_ratio": 0.95,
            "activity_buckets": _demo_activity_buckets(now, "steady"),
        },
    )
    _append_history(history, centre_id="DEMO-KA-303", batch_id="ELEC-2026-06", analysis_type="infrastructure", outcome="attention", summary="Simulated training-panel quantity remained below the required manifest.")

    # Belagavi — verified.
    for analysis_type in ("attendance", "practical_work", "infrastructure"):
        details = (
            {
                "activity_fraction": 0.67,
                "active_work_cells": 3,
                "peak_stable_workers": 5,
                "trusted_frame_ratio": 0.96,
                "activity_buckets": _demo_activity_buckets(now, "steady"),
            }
            if analysis_type == "practical_work"
            else None
        )
        _append_history(
            history,
            centre_id="DEMO-KA-509",
            batch_id="ELEC-2026-10",
            analysis_type=analysis_type,
            outcome="compliant",
            summary=f"Simulated {analysis_type.replace('_', ' ')} evidence aligned.",
            details=details,
        )

    # Mangaluru intentionally receives no analysis rows: ANALYSIS UNAVAILABLE.

    return {
        "prepared": True,
        "simulated": True,
        "data_dir": str(data_dir),
        "reset": reset_result,
        "cases": [case.case_id for case in cases],
        "evidence": [
            {
                "evidence_id": evidence_primary.evidence_id,
                "sha256": evidence_primary.sha256,
                "duplicate_of": evidence_primary.duplicate_of,
            },
            {
                "evidence_id": evidence_duplicate.evidence_id,
                "sha256": evidence_duplicate.sha256,
                "duplicate_of": evidence_duplicate.duplicate_of,
            },
        ],
        "expected_network_states": {
            "DEMO-KA-104": "NEEDS REVIEW",
            "DEMO-KA-112": "VERIFIED",
            "DEMO-KA-207": "UNCERTAIN",
            "DEMO-KA-303": "NEEDS REVIEW",
            "DEMO-KA-509": "VERIFIED",
            "DEMO-KA-601": "ANALYSIS UNAVAILABLE",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare deterministic simulated KaushalWatch runtime state for the SIH walkthrough."
    )
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA))
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Reset mutable runtime state and write the simulated demo seed.",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir).expanduser().resolve()
    if not args.yes:
        print(json.dumps({
            "dry_run": True,
            "data_dir": str(data_dir),
            "action": "reset mutable runtime state, then write clearly simulated cases/history/evidence",
            "preserves_raw": True,
        }, indent=2))
        return

    print(json.dumps(prepare_demo_state(data_dir), indent=2))


if __name__ == "__main__":
    main()
