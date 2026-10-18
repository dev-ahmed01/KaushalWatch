"""Durable, auditable Camera Trust shadow persistence; never writes kw_cases.

Explicit migration 0003 required. All mutation functions use database transactions
with row locks and per-camera audit sequence locks; API never accepts an actor ID.
"""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
import uuid

from fastapi import HTTPException
from psycopg.types.json import Jsonb
from app.services.postgres_store import connection

def _uid() -> str:
    return str(uuid.uuid4())

def _stamp(value) -> str | None:
    return value.isoformat() if value is not None else None

def _json_hash(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                      ensure_ascii=True, allow_nan=False).encode()).hexdigest()

def _audit(db, camera_id: str, actor: str, event: str, payload: dict) -> None:
    # Every writer locks its parent camera BEFORE allocating next sequence.
    previous = db.execute(
        "SELECT sequence,event_sha256 FROM kw_camera_audit WHERE camera_id=%s ORDER BY sequence DESC LIMIT 1",
        (camera_id,)
    ).fetchone()
    seq = int(previous["sequence"]) + 1 if previous else 1
    prev = previous["event_sha256"] if previous else "0" * 64
    body = {"camera_id": str(camera_id), "sequence": seq, "actor": actor,
            "event": event, "payload": payload, "previous_sha256": prev}
    db.execute("""INSERT INTO kw_camera_audit
       (event_id,camera_id,sequence,actor,event,payload,previous_sha256,event_sha256)
       VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
       (_uid(), camera_id, seq, actor, event, Jsonb(payload), prev, _json_hash(body)))

def _lock_camera(db, centre_id: str, camera_id: str) -> dict:
    row = db.execute(
        "SELECT * FROM kw_camera_registry WHERE centre_id=%s AND camera_id=%s FOR UPDATE",
        (centre_id, camera_id)).fetchone()
    if row is None:
        raise HTTPException(404, "Camera not found")
    return row

def _camera(row: dict) -> dict:
    return {"camera_id": str(row["camera_id"]), "centre_id": row["centre_id"],
            "label": row["label"], "source_alias": row["source_alias"],
            "created_at": _stamp(row["created_at"]),
            "physical_health": "UNKNOWN", "production_qualified": False}

def register_camera(centre_id: str, label: str, alias: str, actor: str) -> dict:
    cid = _uid()
    with connection() as db:
        if db.execute("SELECT 1 FROM kw_camera_registry WHERE centre_id=%s AND label=%s",
                      (centre_id,label)).fetchone():
            raise HTTPException(409, "Camera label already registered")
        row = db.execute("""INSERT INTO kw_camera_registry
           (camera_id,centre_id,label,source_alias,created_by)
           VALUES(%s,%s,%s,%s,%s) RETURNING *""",
           (cid,centre_id,label,alias,actor)).fetchone()
        _audit(db,cid,actor,"camera_registered",{"label":label,"source_alias":alias})
    return _camera(row)

def list_cameras(centre_id: str) -> list[dict]:
    with connection() as db:
        rows = db.execute("""SELECT * FROM kw_camera_registry WHERE centre_id=%s
                              ORDER BY created_at DESC""",(centre_id,)).fetchall()
    return [_camera(r) for r in rows]

def propose_reference(centre_id: str, camera_id: str, sha: str, captured: datetime,
                      note: str, actor: str) -> dict:
    rid = _uid()
    with connection() as db:
        _lock_camera(db,centre_id,camera_id)
        db.execute("""INSERT INTO kw_camera_references
          (reference_id,camera_id,sha256,captured_at,note,proposed_by,status)
          VALUES(%s,%s,%s,%s,%s,%s,'proposed')""",
          (rid,camera_id,sha,captured,note,actor))
        _audit(db,camera_id,actor,"reference_proposed",
               {"reference_id":rid,"sha256":sha,"physical_custody_verified":False})
    return {"reference_id":rid,"status":"proposed","physical_custody_verified":False}

def decide_reference(centre_id: str, camera_id: str, reference_id: str,
                     approve: bool, actor: str) -> dict:
    with connection() as db:
        _lock_camera(db,centre_id,camera_id)
        row = db.execute("""SELECT * FROM kw_camera_references
          WHERE reference_id=%s AND camera_id=%s FOR UPDATE""",
          (reference_id,camera_id)).fetchone()
        if row is None:
            raise HTTPException(404, "Reference proposal not found")
        if row["status"] != "proposed":
            raise HTTPException(409, "Reference proposal already decided")
        if row["proposed_by"] == actor:
            raise HTTPException(403, "Reference proposer cannot approve or reject their own proposal")
        if approve and db.execute("""SELECT 1 FROM kw_camera_references
          WHERE camera_id=%s AND status='approved'""",(camera_id,)).fetchone():
            raise HTTPException(409, "Existing approved reference requires a separate explicit retirement procedure")
        status = "approved" if approve else "rejected"
        db.execute("""UPDATE kw_camera_references
          SET status=%s,approved_by=%s,approved_at=NOW() WHERE reference_id=%s""",
          (status,actor,reference_id))
        _audit(db,camera_id,actor,"reference_"+status,{"reference_id":reference_id})
    return {"reference_id":reference_id,"status":status,
            "physical_custody_verified":False}

def list_references(centre_id: str, camera_id: str) -> list[dict]:
    with connection() as db:
        _lock_camera(db,centre_id,camera_id)
        rows=db.execute("""SELECT reference_id,sha256,captured_at,proposed_at,
          proposed_by,approved_by,approved_at,status FROM kw_camera_references
          WHERE camera_id=%s ORDER BY proposed_at DESC""",(camera_id,)).fetchall()
    return [{**r,"reference_id":str(r["reference_id"]),
             **{k:_stamp(r[k]) for k in ("captured_at","proposed_at","approved_at")}}
            for r in rows]

def queue_job(centre_id: str, camera_id: str, source_alias: str, sha: str,
              key: str, sample_limit: int, actor: str) -> dict:
    jid = _uid()
    with connection() as db:
        cam=_lock_camera(db,centre_id,camera_id)
        if cam["source_alias"] != source_alias:
            raise HTTPException(409,"Source does not match this camera's enrolled alias")
        row=db.execute("""INSERT INTO kw_camera_jobs
          (job_id,camera_id,source_alias,source_sha256,idempotency_key,status,sample_limit,created_by)
          VALUES(%s,%s,%s,%s,%s,'queued',%s,%s)
          ON CONFLICT(camera_id,idempotency_key) DO NOTHING RETURNING job_id,status""",
          (jid,camera_id,source_alias,sha,key,sample_limit,actor)).fetchone()
        if row is None:
            old=db.execute("""SELECT job_id,status,source_sha256 FROM kw_camera_jobs
              WHERE camera_id=%s AND idempotency_key=%s""",(camera_id,key)).fetchone()
            if old["source_sha256"] != sha:
                raise HTTPException(409,"Idempotency key already used for another source version")
            return {"job_id":str(old["job_id"]),"status":old["status"],"replayed":True}
        _audit(db,camera_id,actor,"analysis_queued",{"job_id":jid,"source_sha256":sha})
    return {"job_id":jid,"status":"queued","replayed":False}

def list_jobs(centre_id: str,camera_id: str) -> list[dict]:
    with connection() as db:
        _lock_camera(db,centre_id,camera_id)
        rows=db.execute("""SELECT job_id,status,attempts,last_error,created_at,updated_at
          FROM kw_camera_jobs WHERE camera_id=%s ORDER BY created_at DESC LIMIT 100""",
          (camera_id,)).fetchall()
    return [{**r,"job_id":str(r["job_id"]),
             "created_at":_stamp(r["created_at"]),"updated_at":_stamp(r["updated_at"])}
            for r in rows]

def cancel_job(centre_id: str,camera_id: str,job_id: str,actor: str) -> dict:
    with connection() as db:
        _lock_camera(db,centre_id,camera_id)
        row=db.execute("""UPDATE kw_camera_jobs
          SET status='cancelled',updated_at=NOW(),leased_until=NULL,worker_id=NULL
          WHERE camera_id=%s AND job_id=%s AND status='queued' RETURNING job_id""",
          (camera_id,job_id)).fetchone()
        if row is None:
            raise HTTPException(409,"Only queued jobs can be cancelled")
        _audit(db,camera_id,actor,"analysis_cancelled",{"job_id":job_id})
    return {"job_id":job_id,"status":"cancelled"}

def observations(centre_id: str,camera_id: str) -> list[dict]:
    with connection() as db:
        _lock_camera(db,centre_id,camera_id)
        rows=db.execute("""SELECT observation_id,job_id,created_at,payload,
          review_status,reviewer,review_note,reviewed_at
          FROM kw_camera_observations WHERE camera_id=%s
          ORDER BY created_at DESC LIMIT 100""",(camera_id,)).fetchall()
    return [{**r,"observation_id":str(r["observation_id"]),
             "job_id":str(r["job_id"]),"created_at":_stamp(r["created_at"]),
             "reviewed_at":_stamp(r["reviewed_at"])} for r in rows]

def review_observation(centre_id: str,camera_id: str,obs_id: str,
                       outcome: str,note: str,actor: str) -> dict:
    with connection() as db:
        _lock_camera(db,centre_id,camera_id)
        row=db.execute("""SELECT review_status FROM kw_camera_observations
          WHERE observation_id=%s AND camera_id=%s FOR UPDATE""",
          (obs_id,camera_id)).fetchone()
        if not row:raise HTTPException(404,"Observation not found")
        if row["review_status"] != "unreviewed":
            raise HTTPException(409,"Observation already reviewed; original decision retained")
        db.execute("""UPDATE kw_camera_observations SET review_status=%s,
          reviewer=%s,review_note=%s,reviewed_at=NOW()
          WHERE observation_id=%s""",(outcome,actor,note,obs_id))
        _audit(db,camera_id,actor,"observation_reviewed",
               {"observation_id":obs_id,"decision":outcome,"note":note})
    return {"observation_id":obs_id,"review_status":outcome}

def audit_events(centre_id: str,camera_id: str) -> list[dict]:
    with connection() as db:
        _lock_camera(db,centre_id,camera_id)
        rows=db.execute("""SELECT sequence,actor,event,payload,previous_sha256,
          event_sha256,created_at FROM kw_camera_audit WHERE camera_id=%s
          ORDER BY sequence ASC LIMIT 2000""",(camera_id,)).fetchall()
    return [{**r,"created_at":_stamp(r["created_at"])} for r in rows]

def claim(worker_id: str) -> dict | None:
    with connection() as db:
        row=db.execute("""SELECT j.*,r.centre_id FROM kw_camera_jobs j
          JOIN kw_camera_registry r ON r.camera_id=j.camera_id
          WHERE ((j.status='queued') OR
                 (j.status='running' AND j.leased_until<NOW()))
                 AND j.attempts < 3
          ORDER BY j.created_at FOR UPDATE OF j SKIP LOCKED LIMIT 1""").fetchone()
        if not row:return None
        db.execute("""UPDATE kw_camera_jobs SET status='running',attempts=attempts+1,
          worker_id=%s,leased_until=NOW()+INTERVAL '45 minutes',updated_at=NOW()
          WHERE job_id=%s""",(worker_id,row["job_id"]))
        row=dict(row)
        row["job_id"]=str(row["job_id"]);row["camera_id"]=str(row["camera_id"])
        return row

def finish(job: dict, payload: dict, worker_id: str) -> bool:
    with connection() as db:
        cam=db.execute("SELECT camera_id FROM kw_camera_registry WHERE camera_id=%s FOR UPDATE",
                       (job["camera_id"],)).fetchone()
        if not cam:raise RuntimeError("Missing camera")
        held=db.execute("""SELECT status,worker_id FROM kw_camera_jobs
          WHERE job_id=%s FOR UPDATE""",(job["job_id"],)).fetchone()
        if held["status"]!="running" or held["worker_id"]!=worker_id:return False
        ref=db.execute("""SELECT reference_id FROM kw_camera_references
          WHERE camera_id=%s AND status='approved'""",(job["camera_id"],)).fetchone()
        obs=_uid()
        db.execute("""INSERT INTO kw_camera_observations
          (observation_id,camera_id,job_id,source_sha256,reference_id,payload)
          VALUES(%s,%s,%s,%s,%s,%s)""",
          (obs,job["camera_id"],job["job_id"],job["source_sha256"],
           ref["reference_id"] if ref else None,Jsonb(payload)))
        db.execute("""UPDATE kw_camera_jobs SET status='succeeded',
          updated_at=NOW(),leased_until=NULL,worker_id=NULL,last_error=NULL
          WHERE job_id=%s""",(job["job_id"],))
        _audit(db,job["camera_id"],"camera_worker","analysis_completed",
               {"job_id":job["job_id"],"observation_id":obs,"result":"shadow_only"})
    return True

def fail(job: dict, worker_id: str, category: str) -> None:
    with connection() as db:
        cam=db.execute("SELECT camera_id FROM kw_camera_registry WHERE camera_id=%s FOR UPDATE",
                       (job["camera_id"],)).fetchone()
        if not cam:return
        row=db.execute("""SELECT status,worker_id,attempts FROM kw_camera_jobs
          WHERE job_id=%s FOR UPDATE""",(job["job_id"],)).fetchone()
        if row["status"]!="running" or row["worker_id"]!=worker_id:return
        status="queued" if row["attempts"]<3 else "failed"
        db.execute("""UPDATE kw_camera_jobs SET status=%s,worker_id=NULL,
          leased_until=NULL,last_error=%s,updated_at=NOW() WHERE job_id=%s""",
          (status,category,job["job_id"]))
        _audit(db,job["camera_id"],"camera_worker","analysis_"+status,
               {"job_id":job["job_id"],"error_type":category})
