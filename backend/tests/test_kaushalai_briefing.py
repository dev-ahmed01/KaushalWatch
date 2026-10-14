import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BACKEND))

from app.services.analysis_history import AnalysisHistoryStore
from app.services.case_store import CaseStore
from app.services.demo_network import DEMO_CENTRES, centre_rows
from app.services.kaushalai_briefing import build_network_brief
from scripts.prepare_demo_state import prepare_demo_state


def test_grounded_brief_uses_five_centres_and_ranks_current_risk(tmp_path):
    data = tmp_path / "data"
    prepare_demo_state(data)

    store = CaseStore(data / "cases.json")
    history = AnalysisHistoryStore(data / "analysis_history.json")
    grouped = {
        centre["centre_id"]: history.list(centre_id=centre["centre_id"], limit=200)
        for centre in DEMO_CENTRES
    }
    centres = centre_rows(store.list(), history_by_centre=grouped)

    brief = build_network_brief(
        centres=centres,
        cases=store.list(),
        history=history.list(limit=500),
        period="last_7_days",
        now=datetime.now(timezone.utc),
    )

    assert brief["grounded"] is True
    assert brief["simulated"] is True
    assert brief["counts"] == {
        "total": 5,
        "verified": 2,
        "review": 2,
        "uncertain": 1,
        "unavailable": 0,
    }
    assert len(brief["centres"]) == 5
    assert all(row["centre_id"] != "DEMO-KA-601" for row in brief["centres"])
    assert brief["period_activity"]["analysis_runs"] == 15
    assert brief["period_activity"]["attention_or_blocked_runs"] == 5
    assert brief["priority"]["centre_id"] == "DEMO-KA-303"
    assert brief["priority"]["label"] == "Review infrastructure evidence"

    tumakuru = next(
        row for row in brief["centres"]
        if row["centre_id"] == "DEMO-KA-207"
    )
    assert tumakuru["state"] == "uncertain"
    assert "camera trust" in tumakuru["reason"].lower()


def test_empty_selected_period_keeps_current_state_and_says_no_new_runs(tmp_path):
    data = tmp_path / "data"
    prepare_demo_state(data)

    store = CaseStore(data / "cases.json")
    history = AnalysisHistoryStore(data / "analysis_history.json")
    grouped = {
        centre["centre_id"]: history.list(centre_id=centre["centre_id"], limit=200)
        for centre in DEMO_CENTRES
    }
    centres = centre_rows(store.list(), history_by_centre=grouped)

    brief = build_network_brief(
        centres=centres,
        cases=store.list(),
        history=history.list(limit=500),
        period="yesterday",
        now=datetime.now(timezone.utc),
    )

    assert brief["period_activity"]["analysis_runs"] == 0
    assert brief["counts"]["review"] == 2
    assert brief["counts"]["uncertain"] == 1
    assert any("No new analysis runs" in line for line in brief["bullets"])
