import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))

from app.models import ComplianceCase, EvidenceRecord
from edge.agent import case_to_edge_payload, scheduled_window_key


def test_edge_payload_excludes_local_evidence_path_and_identity():
    evidence = EvidenceRecord(
        evidence_id="EV-1",
        created_at="2026-10-03T00:00:00+00:00",
        frame_path="/private/local/evidence.jpg",
        sha256="a" * 64,
        perceptual_hash="1234567890abcdef",
        metadata={"privacy_transform": "person_regions_blurred_before_central_retention"},
    )
    case = ComplianceCase(
        case_id="CASE-1",
        centre_id="DEMO",
        batch_id="B1",
        case_type="attendance_discrepancy",
        severity="high",
        summary="demo",
        evidence=[evidence],
    )

    payload = case_to_edge_payload(case)
    encoded = str(payload)

    assert "/private/local/evidence.jpg" not in encoded
    assert payload["privacy"]["raw_video_included"] is False
    assert payload["privacy"]["individual_identification"] is False
    assert payload["evidence_integrity"][0]["sha256"] == "a" * 64



def test_scheduled_window_key_triggers_once_inside_configured_window():
    settings = {
        "automatic_analysis": True,
        "frequency": "every_training_day",
        "monitoring_windows": ["09:00-11:00", "14:00-16:00"],
    }
    due = scheduled_window_key(settings, datetime(2026, 10, 5, 9, 30))
    assert due == "2026-10-05|09:00-11:00"

    outside = scheduled_window_key(settings, datetime(2026, 10, 5, 12, 30))
    assert outside is None

    manual = scheduled_window_key(
        {**settings, "frequency": "manual"},
        datetime(2026, 10, 5, 9, 30),
    )
    assert manual is None
