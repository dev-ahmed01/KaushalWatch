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
    dsn=os.environ["KAUSHALWATCH_DATABASE_URL"]
    with psycopg.connect(dsn) as db:
        existing_cases=db.execute("SELECT COUNT(*) FROM kw_cases").fetchone()[0]
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
    with pytest.raises(Exception) as different_samples:
        store.queue_job(C,cid,"synthetic.avi",SHA,"synthetic-run-v01",49,"officer-B")
    assert different_samples.value.status_code==409
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
    assert cases==existing_cases

def test_queue_cancel_never_cancels_running_job():
    cam=store.register_camera(C,"Second synthetic camera","synthetic-2.avi","officer-A")
    cid=cam["camera_id"]
    queued=store.queue_job(C,cid,"synthetic-2.avi",SHA,"synthetic-run-v02",12,"officer-A")
    assert store.cancel_job(C,cid,queued["job_id"],"officer-A")["status"]=="cancelled"
    with pytest.raises(Exception) as again:
        store.cancel_job(C,cid,queued["job_id"],"officer-A")
    assert again.value.status_code==409
    assert store.claim("CI-TEST")==None

def test_full_private_worker_route_on_synthetic_original_video(tmp_path,monkeypatch):
    """DB enqueue -> worker claim -> fake Drive copy -> decode -> stored review."""
    import hashlib
    import json
    import shutil
    import cv2
    import numpy as np
    from scripts import run_camera_trust_worker as worker

    source=tmp_path/"synthetic.avi"
    writer=cv2.VideoWriter(str(source),cv2.VideoWriter_fourcc(*"MJPG"),6,(128,96))
    assert writer.isOpened(), "CI FFmpeg MJPG encoder required"
    for i in range(30):
        frame=np.full((96,128,3),40+(i%10)*12,dtype=np.uint8)
        cv2.putText(frame,str(i),(10,40),cv2.FONT_HERSHEY_SIMPLEX,.65,(255,255,255),2)
        writer.write(frame)
    writer.release()
    sha=hashlib.sha256(source.read_bytes()).hexdigest()
    manifest=tmp_path/"manifest.json"
    manifest.write_text(json.dumps({"version":"KWTRUST_DRIVE_ASSETS_V1",
       "files":[{"id":"A"*25,"name":"synthetic.avi","sha256":sha,"group":"full-videos"}]}))
    monkeypatch.setenv("KAUSHALWATCH_CAMERA_SOURCE_GRANTS_JSON",
                       json.dumps({C:["synthetic.avi"]}))
    cam=store.register_camera(C,"CI replay camera","synthetic.avi","officer-A")
    jid=store.queue_job(C,cam["camera_id"],"synthetic.avi",sha,"ci-synthetic-replay-001",12,
                        "officer-A")["job_id"]
    def controlled_private_download(item,dest,token,client_secret):
        assert item["sha256"]==sha
        shutil.copy2(source,dest/item["name"])
    monkeypatch.setattr(worker,"fetch_approved_file",controlled_private_download)
    assert worker.run_one(manifest,tmp_path/"cache",tmp_path/"refs",None,None,"ci-worker-A")
    jobs=store.list_jobs(C,cam["camera_id"])
    assert len(jobs)==1 and jobs[0]["status"]=="succeeded"
    obs=store.observations(C,cam["camera_id"])
    assert len(obs)==1
    data=obs[0]["payload"]
    assert data["sampled_frames"]==12 and data["requested_samples"]==12
    assert data["failed_positions"]==[]
    assert data["production_qualified"] is False
    assert data["authorized_reference_file_present"] is False
    assert data["physical_camera_health"]=="UNKNOWN"
    assert data["source_sha256"]==sha
    assert data["auto_incident_mutations"]==0
    assert data["frame_images_or_video_exported"] is False
    assert all(row["geometry"]["state"]=="UNKNOWN_NO_APPROVED_REFERENCE" for row in data["samples"])
    assert worker.run_one(manifest,tmp_path/"cache",tmp_path/"refs",None,None,"ci-worker-B") is False
    assert len(store.observations(C,cam["camera_id"]))==1
