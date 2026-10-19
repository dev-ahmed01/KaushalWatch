"""Private dedicated Camera Trust worker. No chat uploads or public media URLs.

An authorized runtime needs a SHA-pinned private manifest and Google ADC or a
pre-authorized OAuth token. The worker runs separately from the FastAPI server.
Original media never enters GitHub, browser or model conversation.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import socket
import sys
import time
from threading import Event, Thread

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"backend"))

import cv2
from app.services import camera_trust_store as store
from app.services.camera_quality import sample
from app.services.camera_sources import require_source
from camera_trust_workstation.kwtrust.drive_sync import (
    _authorize, load_manifest, sha256_file, sync_one,
)

def authorized_sources(path: Path, centre_id: str, name: str, expected_sha: str) -> dict:
    manifest=load_manifest(path)
    item=require_source(centre_id,name,manifest)
    if item.get("sha256")!=expected_sha:
        raise ValueError("Frozen source hash changed since job submission")
    return item

def reference_image(camera_id: str, reference_dir: Path):
    from app.services.postgres_store import connection
    with connection() as db:
        row=db.execute("""SELECT sha256,reference_id FROM kw_camera_references
          WHERE camera_id=%s AND status='approved'""",(camera_id,)).fetchone()
    if row is None:return None,None
    path=reference_dir/(row["sha256"]+".png")
    if not path.is_file() or sha256_file(path)!=row["sha256"]:
        # Never substitute first source frame as a custodial reference.
        return None,None
    frame=cv2.imread(str(path),cv2.IMREAD_COLOR)
    return (frame,str(row["reference_id"])) if frame is not None else (None,None)

def analyze_video(path: Path, job: dict, reference, heartbeat=None) -> dict:
    capture=cv2.VideoCapture(str(path))
    if not capture.isOpened():raise ValueError("Video cannot be decoded")
    try:
        total=int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        fps=float(capture.get(cv2.CAP_PROP_FPS))
        if total<2 or total>2_000_000 or not (0.1<=fps<=240):
            raise ValueError("Video frame metadata outside supported range")
        # Source-wide deterministic sparse inspection, never claimed to be full decode.
        n=min(int(job["sample_limit"]),total)
        positions=sorted({round(i*(total-1)/max(1,n-1)) for i in range(n)})
        previous=None;results=[];failed=[]
        for idx,pos in enumerate(positions):
            if heartbeat and idx%4==0 and not heartbeat():
                raise RuntimeError("Worker lease was lost; do not persist stale result")
            capture.set(cv2.CAP_PROP_POS_FRAMES,int(pos))
            ok,frame=capture.read()
            observed=int(round(capture.get(cv2.CAP_PROP_POS_FRAMES)))-1
            if not ok or frame is None or abs(observed-pos)>1:
                failed.append(pos);continue
            outcome=sample(frame,reference,previous)
            results.append({"requested_frame0":pos,"decoded_frame0":observed,
                            "time_seconds_estimated":round(observed/fps,3),
                            **outcome})
            previous=frame
        if not results:raise ValueError("No decodable positions")
        return {"schema":"CAMERA_TRUST_SHADOW_SAMPLE_V1",
                "source_sha256":job["source_sha256"],
                "sampled_frames":len(results),"requested_samples":len(positions),
                "failed_positions":failed,"source_frame_count_reported":total,
                "fps_reported":fps,"sampling":"SPARSE_RANDOM_ACCESS_NOT_FULL_VIDEO_DECODE",
                "possible_review_samples":sum(bool(x["candidate_for_human_review"]) for x in results),
                "physical_camera_health":"UNKNOWN",
                "production_qualified":False,"auto_incident_mutations":0,
                "frame_images_or_video_exported":False,"samples":results}
    finally:capture.release()

def heartbeat(job: dict, worker_id: str) -> bool:
    from app.services.postgres_store import connection
    with connection() as db:
        row=db.execute("""UPDATE kw_camera_jobs SET leased_until=NOW()+INTERVAL '45 minutes',
          updated_at=NOW() WHERE job_id=%s AND camera_id=%s AND worker_id=%s
          AND attempts=%s AND status='running' AND leased_until>NOW()
          RETURNING job_id""",
          (job["job_id"],job["camera_id"],worker_id,job.get("attempts"))).fetchone()
    return row is not None

def fetch_approved_file(item: dict, dest: Path, token: Path | None,
                        client_secret: Path | None) -> None:
    """One authenticated transfer boundary, injectable in synthetic tests."""
    creds=_authorize(token,client_secret,headless=True)
    from google.auth.transport.requests import AuthorizedSession
    sync_one(AuthorizedSession(creds),item,dest)

def run_one(manifest: Path, dest: Path, refs: Path, token: Path | None,
            client_secret: Path | None, worker_id: str) -> bool:
    job=store.claim(worker_id)
    if not job:return False
    stop=Event()
    def renew_lease():
        # Preserve ownership during long private source downloads.
        while not stop.wait(60):
            try:
                if not heartbeat(job,worker_id):stop.set()
            except Exception:
                stop.set()
    keeper=Thread(target=renew_lease,daemon=True)
    keeper.start()
    try:
        item=authorized_sources(manifest,job["centre_id"],job["source_alias"],job["source_sha256"])
        dest.mkdir(parents=True,exist_ok=True,mode=0o700)
        fetch_approved_file(item,dest,token,client_secret)
        source=dest/item["name"]
        if stop.is_set() or not heartbeat(job,worker_id):
            raise RuntimeError("Worker lease lost during transfer")
        # Reverify even cached files; never process a changed local source.
        if sha256_file(source)!=job["source_sha256"]:
            raise ValueError("Downloaded file hash differs from enrolled pin")
        ref,reference_id=reference_image(job["camera_id"],refs)
        report=analyze_video(source,job,ref,
                             heartbeat=lambda:not stop.is_set() and heartbeat(job,worker_id))
        report["approved_reference_id"]=reference_id
        report["authorized_reference_file_present"]=reference_id is not None
        report["physical_reference_custody_verified"]=False
        if stop.is_set():raise RuntimeError("Worker lease lost")
        store.finish(job,report,worker_id)
    except Exception as exc:
        # Never persist paths, source IDs, tokens or exception string in DB.
        store.fail(job,worker_id,type(exc).__name__)
    finally:
        stop.set()
        keeper.join(timeout=2)
    return True

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--once",action="store_true")
    p.add_argument("--preflight",action="store_true",
                   help="Validate worker setup without claiming or running jobs")
    p.add_argument("--poll-seconds",type=int,default=15)
    args=p.parse_args()
    if os.getenv("KAUSHALWATCH_STORAGE_BACKEND")!="postgres":
        p.error("Camera Trust worker requires PostgreSQL")
    manifest=Path(os.environ.get("KAUSHALWATCH_CAMERA_DRIVE_MANIFEST",""))
    if not manifest.is_file():p.error("Approved private Drive manifest is missing")
    dest=Path(os.environ.get("KAUSHALWATCH_CAMERA_MEDIA_DIR",".private/camera-media"))
    refs=Path(os.environ.get("KAUSHALWATCH_CAMERA_REFERENCE_DIR",".private/camera-references"))
    token=os.getenv("KAUSHALWATCH_CAMERA_DRIVE_TOKEN")
    secret=os.getenv("KAUSHALWATCH_CAMERA_DRIVE_OAUTH_CLIENT")
    token_path=Path(token) if token else None
    secret_path=Path(secret) if secret else None
    # Credential and DB preflight happens before claiming a job; wrong
    # deployment configuration must not consume three processing attempts.
    try:
        file_rows=load_manifest(manifest)
        from app.services.camera_sources import permitted_aliases
        from app.services.demo_network import provisioned_centres
        for centre in provisioned_centres():
            permitted_aliases(centre["centre_id"],file_rows)
        from app.services.postgres_store import connection
        with connection() as db:
            if db.execute("SELECT to_regclass('kw_camera_jobs') AS table_name").fetchone()["table_name"] is None:
                raise RuntimeError("Camera Trust PostgreSQL migration missing")
        if not args.preflight:
            _authorize(token_path,secret_path,headless=True)
    except Exception as exc:
        p.error("Camera Trust worker configuration unavailable: "+type(exc).__name__)
    if args.preflight:
        print("Camera Trust worker configuration validated (no media transferred).")
        return
    worker_id=(socket.gethostname()[:40]+"-"+str(os.getpid()))
    while True:
        had_job=run_one(manifest,dest,refs,token_path,secret_path,worker_id)
        if args.once:break
        if not had_job:time.sleep(max(3,min(args.poll_seconds,3600)))

if __name__=="__main__":
    main()
