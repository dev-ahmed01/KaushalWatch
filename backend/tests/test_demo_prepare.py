import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BACKEND))

from app.services.analysis_history import AnalysisHistoryStore
from app.services.case_store import CaseStore
from app.services.demo_network import DEMO_CENTRES, centre_rows
from scripts.prepare_demo_state import prepare_demo_state


def test_prepared_demo_state_matches_the_locked_six_centre_story(tmp_path):
    data = tmp_path / "data"
    result = prepare_demo_state(data)

    assert result["prepared"] is True
    assert result["simulated"] is True
    assert result["evidence"][1]["duplicate_of"] == "SIM-EV-KA104-01"

    store = CaseStore(data / "cases.json")
    history = AnalysisHistoryStore(data / "analysis_history.json")
    grouped = {
        centre["centre_id"]: history.list(centre_id=centre["centre_id"], limit=20)
        for centre in DEMO_CENTRES
    }
    rows = {
        row["centre_id"]: row
        for row in centre_rows(store.list(), history_by_centre=grouped)
    }

    assert all(
        centre["job_role"] == "Construction Electrician - LV"
        for centre in DEMO_CENTRES
    )

    assert rows["DEMO-KA-104"]["status"] == "attention"
    assert rows["DEMO-KA-104"]["attendance_status"] == "attention"

    assert rows["DEMO-KA-112"]["status"] == "compliant"
    assert rows["DEMO-KA-509"]["status"] == "compliant"

    assert rows["DEMO-KA-207"]["camera_status"] == "attention"
    assert rows["DEMO-KA-207"]["attendance_status"] == "blocked"
    assert rows["DEMO-KA-207"]["practical_status"] == "blocked"
    assert rows["DEMO-KA-207"]["infrastructure_status"] == "blocked"

    assert rows["DEMO-KA-303"]["status"] == "high_priority"
    assert rows["DEMO-KA-303"]["infrastructure_status"] == "attention"
    assert rows["DEMO-KA-303"]["escalation"]["level"] >= 3

    assert rows["DEMO-KA-601"]["status"] == "incomplete"
    assert rows["DEMO-KA-601"]["analysis_count"] == 0
