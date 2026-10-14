"""Regression checks for review findings before promoting the restructure to main."""
from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.models import ComplianceCase
from app.services.evidence_review import _history_temporal_points
from app.services.activity_intelligence import _merge_adjacent_low_periods, build_activity_intelligence


def test_temporal_proof_restricts_batch_and_never_uses_future_or_stale_analyses():
    t = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
    case = ComplianceCase(
        case_id="TEST-AUDIT-C1", centre_id="CENTRE-101",
        batch_id="BATCH-ONE", case_type="attendance_discrepancy",
        severity="medium", summary="Grounded synthetic attendance discrepancy",
        created_at=t.isoformat(),
    )
    def row(batch,when,outcome="attention",centre="CENTRE-101"):
        return {"analysis_type":"attendance","batch_id":batch,"centre_id":centre,
                "created_at":when.isoformat(),"outcome":outcome,
                "summary":f"Verified analysis {batch}"}
    history = [
        row("BATCH-OTHER",t-timedelta(minutes=12)),
        row("BATCH-ONE",t-timedelta(days=4)),
        row("BATCH-ONE",t+timedelta(minutes=10)),
        row("BATCH-ONE",t-timedelta(minutes=5),"attention","CENTRE-999"),
        row("BATCH-ONE",t-timedelta(minutes=3)),
    ]
    result = _history_temporal_points(case,history)
    assert len(result) == 1
    assert result[0]["state"] == "miss"
    assert result[0]["note"] == "Verified analysis BATCH-ONE"


def test_activity_windows_do_not_count_unobserved_gap_as_low_activity():
    tz=timezone(timedelta(hours=5,minutes=30))
    start=datetime(2026,10,14,12,0,tzinfo=tz)
    buckets=[
        {"start":start,"end":start+timedelta(minutes=10),
         "activity_score":0.10,"trusted_frame_ratio":1.0,
         "active_work_cells":1,"simulated":False,"source":"test"},
        {"start":start+timedelta(minutes=25),
         "end":start+timedelta(minutes=35),
         "activity_score":0.10,"trusted_frame_ratio":1.0,
         "active_work_cells":1,"simulated":False,"source":"test"},
    ]
    separate=_merge_adjacent_low_periods(buckets,0.25)
    assert len(separate)==2
    assert max((x["end"]-x["start"]).total_seconds()/60 for x in separate)==10
    buckets[1]["start"]=buckets[0]["end"]
    consecutive=_merge_adjacent_low_periods(buckets,0.25)
    assert len(consecutive)==1
    assert (consecutive[0]["end"]-consecutive[0]["start"]).total_seconds()/60 == 35


def test_activity_followup_ignores_unobserved_gap_even_when_span_exceeds_threshold():
    tz=timezone(timedelta(hours=5,minutes=30))
    t=datetime(2026,10,14,12,0,tzinfo=tz)
    history=[]
    for n,(a,b) in enumerate([(0,10),(25,35)]):
        history.append({
            "analysis_id":f"test-{n}","centre_id":"CENTRE-101",
            "analysis_type":"practical_work",
            "details":{"activity_buckets":[{
                "start_at":(t+timedelta(minutes=a)).isoformat(),
                "end_at":(t+timedelta(minutes=b)).isoformat(),
                "activity_score":0.1,"trusted_frame_ratio":1.0,
                "active_work_cells":1
            }]}
        })
    report=build_activity_intelligence(
        centre={"centre_id":"CENTRE-101","camera_status":"ok"},
        history=history,period="today",now=t+timedelta(hours=1),
    )
    assert report["state"]=="available"
    assert report["follow_up"]["recommended"] is False
    assert report["summary"]["longest_low_period"]["minutes"]==10.0
