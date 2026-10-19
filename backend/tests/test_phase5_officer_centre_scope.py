"""Phase 5 centre-scoped evidence/read/decision/PDF authorization regression."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import app.main as main
from app.models import ComplianceCase
from app.services.case_store import CaseStore
from app.services.analysis_history import AnalysisHistoryStore

KEY="Synthetic_ReadOnly_Officer_Key_0123456789ABCDEF"

def test_evidence_pack_cannot_enumerate_cross_centre_case_or_report(tmp_path,monkeypatch):
 monkeypatch.setenv("KAUSHALWATCH_ENV","staging")
 monkeypatch.setenv("KAUSHALWATCH_REVIEW_AUTH_MODE","token")
 monkeypatch.setenv("KAUSHALWATCH_REVIEW_TOKENS_JSON",json.dumps({"viewer-phase5":KEY}))
 monkeypatch.setenv("KAUSHALWATCH_OFFICER_PERMISSIONS_JSON",
  json.dumps({"viewer-phase5":{"role":"centre_viewer","centres":["DEMO-KA-104"]}}))
 store=CaseStore(tmp_path/"case-store.json")
 for centre,index in (("DEMO-KA-104","A"),("DEMO-KA-207","B")):
  store.save(ComplianceCase(
   case_id="CASE-PROOF-"+index,centre_id=centre,batch_id="TRAINING-FIXTURE",
   case_type="camera_integrity",severity="medium",
   summary="Generated camera-integrity review",details={
    "simulated":True,"operator_secret":"DO_NOT_RENDER_PRIVATE_METADATA",
    "source_video_sha256":"0"*64,
   }))
 monkeypatch.setattr(main,"STORE",store)
 monkeypatch.setattr(main,"HISTORY",AnalysisHistoryStore(tmp_path/"history.json"))
 client=TestClient(main.app)
 headers={"Authorization":"Bearer "+KEY}
 for path in ("/api/cases/CASE-PROOF-A/evidence-pack",
              "/api/cases/CASE-PROOF-B/evidence-pack",
              "/api/centres/DEMO-KA-207/report.pdf"):
  assert client.get(path).status_code==401
 allowed=client.get("/api/cases/CASE-PROOF-A/evidence-pack",headers=headers)
 assert allowed.status_code==200
 assert allowed.json()["case"]["centre_id"]=="DEMO-KA-104"
 assert allowed.headers["cache-control"]=="private, no-store"
 assert KEY not in allowed.text
 for path in ("/api/cases/CASE-PROOF-B/evidence-pack",
              "/api/centres/DEMO-KA-207/report.pdf"):
  denied=client.get(path,headers=headers)
  assert denied.status_code==404
  assert "DEMO-KA-207" not in denied.text
 write=client.post("/api/cases/CASE-PROOF-A/review",headers=headers,
     json={"action":"under_review","note":"Must not write in read-only role"})
 assert write.status_code==403
 assert store.get("CASE-PROOF-A").review_history==[]
 assert store.get("CASE-PROOF-B").review_history==[]
