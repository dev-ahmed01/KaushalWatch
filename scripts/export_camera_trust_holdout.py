"""Export only SHA-pinned numeric shadow observations named by frozen labels.

Run on a protected PostgreSQL host. No media, images or source aliases leave
the DB boundary. Independent labels must already be frozen outside this app.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"backend"))
from evaluation.camera_trust_holdout import (
    PREDICTION_SCHEMA,_validate_labels,_validate_numeric_trace,
    hash_json,read_json,require,
)

def connection():
    from app.services.postgres_store import connection as postgres_connection
    return postgres_connection()

def sanitize_numeric_report(report:dict,case:dict) -> dict:
    """Allowlist fields after validation: DB JSONB alone is not export-safe."""
    _validate_numeric_trace(report,case)
    top=("schema","source_sha256","physical_camera_health",
         "production_qualified","auto_incident_mutations",
         "frame_images_or_video_exported","sampling",
         "source_frame_count_reported","fps_reported",
         "requested_samples","sampled_frames","failed_positions",
         "possible_review_samples","authorized_reference_file_present")
    fields=("requested_frame0","decoded_frame0","candidate_for_human_review",
            "physical_camera_health","production_qualified")
    clean={key:report[key] for key in top if key in report}
    clean["samples"]=[{key:row[key] for key in fields} for row in report["samples"]]
    return clean

def make_snapshot(labels:dict) -> dict:
    cases=_validate_labels(labels)
    job_ids=[]
    for case_id in cases:
        try:
            uid=uuid.UUID(case_id)
            require(str(uid)==case_id.lower(),"Labels must use canonical UUID job IDs")
        except ValueError:
            require(False,"A label case_id must be an existing UUID job identifier")
        job_ids.append(str(uid))
    with connection() as db:
        rows=db.execute("""SELECT o.job_id,o.camera_id,o.source_sha256,
            o.payload,j.status,r.centre_id FROM kw_camera_observations o
            JOIN kw_camera_jobs j ON j.job_id=o.job_id
            JOIN kw_camera_registry r ON r.camera_id=o.camera_id
            WHERE o.job_id = ANY(%s::uuid[])""",(job_ids,)).fetchall()
    require(len(rows)==len(cases),"Missing or duplicated completed DB observations")
    out=[]
    for row in rows:
        key=str(row["job_id"])
        expected=cases.get(key)
        require(expected is not None,"Unknown job returned by database")
        require(row["status"]=="succeeded" and
                str(row["camera_id"])==expected["camera_id"] and
                row["centre_id"]==expected["site_id"] and
                row["source_sha256"]==expected["source_sha256"],
                "Observation does not match frozen centre/camera/source")
        out.append({"case_id":key,"report":sanitize_numeric_report(row["payload"],expected)})
    return {"schema":PREDICTION_SCHEMA,
            "labels_sha256":hash_json(labels),
            "predictions":sorted(out,key=lambda x:x["case_id"])}

def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--labels",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if os.getenv("KAUSHALWATCH_STORAGE_BACKEND")!="postgres":
        parser.error("Camera Trust export requires protected PostgreSQL")
    snapshot=make_snapshot(read_json(args.labels))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(args.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"w",encoding="utf-8") as out:
        json.dump(snapshot,out,indent=2,sort_keys=True,allow_nan=False)
        out.write("\n");out.flush();os.fsync(out.fileno())
    print("Exported "+str(len(snapshot["predictions"]))+
          " hash-locked numeric cases; no media exported")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
