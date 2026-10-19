"""OS cockpit facts must be scoped and source-backed."""
import sys
from pathlib import Path
from fastapi.testclient import TestClient
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"backend"))
import app.main as app_main
from app.services.analysis_history import AnalysisHistoryStore
from app.services.case_store import CaseStore
from app.services.centre_settings import CentreSettingsStore
from scripts.prepare_demo_state import prepare_demo_state

def setup(tmp_path,monkeypatch):
    data=tmp_path/"data";prepare_demo_state(data)
    monkeypatch.setattr(app_main,"STORE",CaseStore(data/"cases.json"))
    monkeypatch.setattr(app_main,"HISTORY",AnalysisHistoryStore(data/"analysis_history.json"))
    monkeypatch.setattr(app_main,"CENTRE_SETTINGS",CentreSettingsStore(data/"centre_settings.json"))
    monkeypatch.setattr(app_main,"DATA",data)
    return TestClient(app_main.app)

def get(api,cid):
    result=api.get(f"/api/centres/{cid}/intelligence?period=last_7_days")
    assert result.status_code==200
    return result.json()["verification"]

def test_attendance_and_infrastructure_evidence_are_centre_scoped(tmp_path,monkeypatch):
    api=setup(tmp_path,monkeypatch)
    blr=get(api,"DEMO-KA-104")
    assert (blr["attendance"]["reported"],blr["attendance"]["observed"])==(28,19)
    assert blr["attendance"]["source"]=="case"
    assert blr["attendance"]["simulated"] is True
    assert blr["infrastructure"]["reported"] is None
    assert blr["evidence"]["retained_count"]==2
    hub=get(api,"DEMO-KA-303")
    assert (hub["infrastructure"]["reported"],hub["infrastructure"]["observed"])==(12,9)
    assert hub["infrastructure"]["source"]=="case"
    assert (hub["attendance"]["reported"],hub["attendance"]["observed"])==(26,25)
    assert hub["attendance"]["source"]=="analysis"

def test_untrusted_camera_disables_observed_facts(tmp_path,monkeypatch):
    api=setup(tmp_path,monkeypatch)
    blocked=get(api,"DEMO-KA-207")
    assert blocked["camera"]["status"]=="uncertain"
    assert blocked["attendance"]["observed"] is None
    assert blocked["infrastructure"]["observed"] is None
    assert blocked["practical_activity"]["active_work_cells"] is None
    assert blocked["evidence"]["cases_requiring_review"]>=1

def test_empty_centre_has_no_leaked_analyses(tmp_path,monkeypatch):
    api=setup(tmp_path,monkeypatch)
    missing=get(api,"DEMO-KA-601")
    assert missing["attendance"]["observed"] is None
    assert missing["infrastructure"]["observed"] is None
    assert missing["practical_activity"]["active_work_cells"] is None
    assert missing["evidence"]["retained_count"]==0
    mysuru=get(api,"DEMO-KA-112")
    assert (mysuru["attendance"]["reported"],mysuru["attendance"]["observed"])==(24,23)
    assert mysuru["practical_activity"]["active_work_cells"]==3
