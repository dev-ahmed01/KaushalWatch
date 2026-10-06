import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.models import ComplianceCase, EvidenceRecord
from app.services.analysis_history import AnalysisHistoryStore
from app.services.assistant_tools import AssistantDataContext, KaushalToolset
from app.services.case_store import CaseStore
from app.services.demo_network import get_centre


NOW = datetime.now(timezone.utc)
LOCAL_DAY = (NOW + timedelta(hours=5, minutes=30)).date().isoformat()


def _toolset(tmp_path: Path, readiness: dict | None = None):
    history = AnalysisHistoryStore(tmp_path / "analysis_history.json")
    cases = CaseStore(tmp_path / "cases.json")

    def centre_lookup(centre_id: str):
        return get_centre(
            centre_id,
            cases.list(),
            history=history.list(centre_id=centre_id, limit=500),
        )

    context = AssistantDataContext(
        history=history,
        cases=cases,
        centre_lookup=centre_lookup,
        readiness_provider=lambda: readiness or {"attendance": {"ready": False}},
        now_provider=lambda: datetime.now(timezone.utc),
    )
    return KaushalToolset(context), history, cases


def test_operational_history_returns_explicit_local_bounds_when_empty(tmp_path):
    tools, _, _ = _toolset(tmp_path)

    result = tools.get_operational_history("DEMO-KA-104", period="today")

    assert result.data["available"] is False
    assert result.data["count"] == 0
    assert result.data["start_date"] == LOCAL_DAY
    assert result.data["end_date"] == LOCAL_DAY
    assert result.data["timezone"] == "Asia/Kolkata"
    assert result.sources == []


def test_operational_history_filters_by_local_day_and_analysis_type(tmp_path):
    tools, history, _ = _toolset(tmp_path)
    history.append(
        centre_id="DEMO-KA-104",
        batch_id="ELEC-2026-08",
        analysis_type="attendance",
        outcome="attention",
        summary="Attendance issue detected.",
        details={"estimated_occupancy": 2, "frame_path": "private/frame.jpg"},
    )
    history.append(
        centre_id="DEMO-KA-104",
        batch_id="ELEC-2026-08",
        analysis_type="practical_work",
        outcome="compliant",
        summary="Practical activity recorded.",
        details={},
    )

    result = tools.get_operational_history(
        "DEMO-KA-104", period="today", analysis_type="attendance"
    )

    assert result.data["available"] is True
    assert result.data["count"] == 1
    assert result.data["analyses"][0]["summary"] == "Attendance issue detected."
    assert result.data["analyses"][0]["details"] == {"estimated_occupancy": 2}
    assert result.sources[0].kind == "analysis"
    assert result.sources[0].href == "/centres/DEMO-KA-104/history"


def test_operational_history_rejects_unknown_relative_period(tmp_path):
    tools, _, _ = _toolset(tmp_path)

    with pytest.raises(ValueError, match="period must be one of"):
        tools.get_operational_history("DEMO-KA-104", period="last_month")


def test_analysis_details_enforces_centre_ownership(tmp_path):
    tools, history, _ = _toolset(tmp_path)
    row = history.append(
        centre_id="DEMO-KA-112",
        batch_id="FIT-2026-07",
        analysis_type="attendance",
        outcome="compliant",
        summary="Other centre result.",
        details={},
    )

    result = tools.get_analysis_details("DEMO-KA-104", row["analysis_id"])

    assert result.data == {"available": False, "analysis_id": row["analysis_id"]}
    assert result.sources == []


def test_attendance_summary_preserves_data_and_states_identity_limit(tmp_path):
    tools, history, cases = _toolset(tmp_path)
    row = history.append(
        centre_id="DEMO-KA-104",
        batch_id="ELEC-2026-08",
        analysis_type="attendance",
        outcome="attention",
        summary="The system detected a persistent attendance discrepancy.",
        details={
            "reported_attendance": 4,
            "estimated_occupancy": 2,
            "discrepancy_pct": 50.0,
        },
    )
    cases.save(
        ComplianceCase(
            case_id="CASE-ATT-1",
            centre_id="DEMO-KA-104",
            batch_id="ELEC-2026-08",
            case_type="attendance_discrepancy",
            severity="high",
            summary="Attendance mismatch requires review.",
        )
    )

    result = tools.get_attendance_summary("DEMO-KA-104", period="today")

    assert result.data["available"] is True
    assert result.data["analyses"][0]["analysis_id"] == row["analysis_id"]
    assert result.data["analyses"][0]["details"]["estimated_occupancy"] == 2
    assert result.data["worker_identity_available"] is False
    assert "anonymous" in result.data["identity_note"].lower()
    assert result.data["cases"][0]["case_id"] == "CASE-ATT-1"


def test_escalations_use_existing_policy_and_case_evidence_is_compact(tmp_path):
    tools, _, cases = _toolset(tmp_path)
    cases.save(
        ComplianceCase(
            case_id="CASE-EVIDENCE-1",
            centre_id="DEMO-KA-104",
            batch_id="ELEC-2026-08",
            case_type="camera_integrity",
            severity="high",
            summary="Camera feed failed trust checks.",
            reported_attendance=7,
            visual_occupancy=3,
            discrepancy_pct=57.1,
            details={"camera_id": "LAB-CAM-01", "frame_path": "private/frame.jpg"},
            evidence=[
                EvidenceRecord(
                    evidence_id="EV-1",
                    created_at="2026-10-05T06:00:00+00:00",
                    frame_path="private/path/EV-1.jpg",
                    sha256="abc",
                    perceptual_hash="def",
                    metadata={"camera_id": "LAB-CAM-01", "second": 12.5},
                )
            ],
        )
    )

    escalations = tools.get_escalations("DEMO-KA-104", status="unresolved")
    evidence = tools.get_case_evidence("DEMO-KA-104", "CASE-EVIDENCE-1")

    assert escalations.data["available"] is True
    assert escalations.data["escalation"]["label"] == "Centre review"
    assert escalations.data["cases"][0]["severity"] == "high"
    assert escalations.data["cases"][0]["reported_attendance"] == 7
    assert escalations.data["cases"][0]["visual_occupancy"] == 3
    assert escalations.data["cases"][0]["details"] == {"camera_id": "LAB-CAM-01"}
    assert evidence.data["evidence"][0]["evidence_id"] == "EV-1"
    assert "frame_path" not in evidence.data["evidence"][0]
    assert "sha256" not in evidence.data["evidence"][0]
    assert evidence.sources[-1].kind == "evidence"
    assert evidence.sources[-1].href == "/centres/DEMO-KA-104/review"


def test_case_evidence_enforces_centre_ownership(tmp_path):
    tools, _, cases = _toolset(tmp_path)
    cases.save(
        ComplianceCase(
            case_id="CASE-OTHER",
            centre_id="DEMO-KA-112",
            batch_id="FIT-2026-07",
            case_type="attendance_discrepancy",
            severity="medium",
            summary="Other centre case.",
        )
    )

    result = tools.get_case_evidence("DEMO-KA-104", "CASE-OTHER")

    assert result.data == {"available": False, "case_id": "CASE-OTHER"}
    assert result.sources == []


def test_runtime_readiness_tool_returns_shared_provider_result(tmp_path):
    readiness = {
        "attendance": {
            "ready": True,
            "backend": "openvino",
            "authoritative": True,
        }
    }
    tools, _, _ = _toolset(tmp_path, readiness=readiness)

    result = tools.get_runtime_readiness("DEMO-KA-104")

    assert result.data == readiness
    assert result.sources[0].kind == "readiness"
    assert result.sources[0].href == "/centres/DEMO-KA-104/analysis"


def test_network_brief_tool_uses_shared_grounded_provider(tmp_path):
    history = AnalysisHistoryStore(tmp_path / "analysis_history.json")
    cases = CaseStore(tmp_path / "cases.json")

    context = AssistantDataContext(
        history=history,
        cases=cases,
        centre_lookup=lambda _centre_id: None,
        readiness_provider=lambda: {},
        network_brief_provider=lambda period: {
            "generated_at": "2026-10-06T10:00:00+05:30",
            "period": period,
            "headline": "2 of 5 centres are verified.",
            "centres": [
                {
                    "centre_id": "DEMO-KA-104",
                    "name": "Bengaluru TC-04",
                    "href": "/centres/DEMO-KA-104",
                }
            ],
        },
    )

    result = KaushalToolset(context).get_network_brief("last_7_days")

    assert result.data["available"] is True
    assert result.data["period"] == "last_7_days"
    assert result.data["headline"] == "2 of 5 centres are verified."
    assert result.sources[0].kind == "centre"
    assert result.sources[0].href == "/centres/DEMO-KA-104"
