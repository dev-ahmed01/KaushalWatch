"""Isolated PostgreSQL Camera Trust lifecycle/consistency tests.

Must never operate against production data. GitHub CI supplies a disposable
kaushalwatch_ci PostgreSQL database and explicit migration v3.
"""
from __future__ import annotations
from datetime import datetime, timezone
import os
import sys
from pathlib import Path

import psycopg
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.services import camera_trust_store as store

C="DEMO-KA-104"
SHA="a"*64
REFSHA="b"*64

@pytest.fixture(autouse=True)
def isolated_database(monkeypatch):
    dsn=os.getenv("KAUSHALWATCH_DATABASE_URL","")
    if not dsn and not os.getenv("KAUSHALWATCH_TEST_DATABASE"):
        pytest.skip("Camera Trust PostgreSQL lifecycle runs only in CI isolated database")
    if os.getenv("KAUSHALWATCH_TEST_DATABASE")!="isolated_ci" or "kaushalwatch_ci" not in dsn:
        pytest.fail("Refusing Camera Trust DB tests outside an isolated CI database")
    monkeypatch.setenv("KAUSHALWATCH_STORAGE_BACKEND","postgres")
    with psycopg.connect(dsn) as db:
        db.execute("""TRUNCATE kw_camera_audit,kw_camera_observations,
          kw_camera_jobs,kw_camera_references,kw_camera_registry""")
    yield

def test_camera_registry_custody_jobs_reviews_are_isolated_and_audited():
    cam=store.register_camera(C,"Synthetic entrance camera","synthetic.avi","officer-A")
    cid=cam["camera_id"]
    assert cam["production_qualified"] is False
    assert store.list_cameras(C)[0]["camera_id"]==cid
    assert store.list_cameras("DEMO-KA-112")==[]
    with pytest.raises(Exception) as duplicate:
        store.register_camera(C,"Synthetic entrance camera","synthetic.avi","officer-B")
    assert duplicate.value.status_code==409
    proposed=store.propose_reference(C,cid,REFSHA,datetime.now(timezone.utc),
                   "Independent source custody pending review","officer-A")
    rid=proposed["reference_id"]
    with pytest.raises(Exception) as same_actor:
        store.decide_reference(C,cid,rid,True,"officer-A")
    assert same_actor.value.status_code==403
    assert store.decide_reference(C,cid,rid,True,"officer-B")["status"]=="approved"
    with pytest.raises(Exception) as replay:
        store.decide_reference(C,cid,rid,True,"officer-B")
    assert replay.value.status_code==409

    job=store.queue_job(C,cid,"synthetic.avi",SHA,"synthetic-run-v01",48,"officer-A")
    dup=store.queue_job(C,cid,"synthetic.avi",SHA,"synthetic-run-v01",48,"officer-A")
    assert dup["job_id"]==job["job_id"] and dup["replayed"] is True
    with pytest.raises(Exception) as collision:
        store.queue_job(C,cid,"synthetic.avi","c"*64,"synthetic-run-v01",48,"officer-B")
    assert collision.value.status_code==409
    claimed=store.claim("CI-SYNTHETIC-WORKER")
    assert claimed and claimed["job_id"]==job["job_id"]
    assert store.claim("CI-SECOND-WORKER") is None
    report={"schema":"CAMERA_TRUST_SHADOW_SAMPLE_V1","physical_camera_health":"UNKNOWN",
            "production_qualified":False,"approved_reference_id":rid,
            "sampled_frames":1,"auto_incident_mutations":0}
    assert store.finish(claimed,report,"CI-SYNTHETIC-WORKER") is True
    assert store.finish(claimed,report,"CI-SYNTHETIC-WORKER") is False
    observations=store.observations(C,cid)
    assert len(observations)==1
    obs=observations[0]
    assert obs["payload"]["physical_camera_health"]=="UNKNOWN"
    assert store.review_observation(C,cid,obs["observation_id"],
             "needs_followup","Synthetic operator requested physical verification.","officer-B")["review_status"]=="needs_followup"
    with pytest.raises(Exception) as review_twice:
        store.review_observation(C,cid,obs["observation_id"],
             "reviewed","Cannot erase first operator decision.","officer-A")
    assert review_twice.value.status_code==409
    audit=store.audit_events(C,cid)
    assert len(audit)>=5
    prev="0"*64
    for i,event in enumerate(audit,1):
        assert event["sequence"]==i and event["previous_sha256"]==prev
        recomputed=store._json_hash({
            "camera_id":cid,"sequence":event["sequence"],
            "actor":event["actor"],"event":event["event"],
            "payload":event["payload"],"previous_sha256":prev})
        assert event["event_sha256"]==recomputed
        prev=recomputed
    dsn=os.environ["KAUSHALWATCH_DATABASE_URL"]
    with pytest.raises(psycopg.Error):
        with psycopg.connect(dsn) as db:
            db.execute("DELETE FROM kw_camera_audit WHERE camera_id=%s",(cid,))
    with psycopg.connect(dsn) as db:
        cases=db.execute("SELECT COUNT(*) FROM kw_cases").fetchone()[0]
    # Camera pipeline must not create ordinary compliance cases.
    assert cases==0

def test_queue_cancel_never_cancels_running_job():
    cam=store.register_camera(C,"Second synthetic camera","synthetic-2.avi","officer-A")
    cid=cam["camera_id"]
    queued=store.queue_job(C,cid,"synthetic-2.avi",SHA,"synthetic-run-v02",12,"officer-A")
    assert store.cancel_job(C,cid,queued["job_id"],"officer-A")["status"]=="cancelled"
    with pytest.raises(Exception) as again:
        store.cancel_job(C,cid,queued["job_id"],"officer-A")
    assert again.value.status_code==409
    assert store.claim("CI-TEST")==None
