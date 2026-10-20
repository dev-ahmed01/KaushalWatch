"""Prepare deterministic private numeric camera-quality traces for existing local replay.

No source media export, threshold fitting, external requests, or release claim.
Evaluates sparse frames against each video's own UNVERIFIED first frame only.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import sys

import cv2

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/"backend")]
from scripts.prepare_research_replay import prepare
from app.services.camera_quality import sample

SCHEMA="KW_PRIVATE_RESEARCH_TRIAGE_TRACE_V1"
ORIGIN="MEVA_UHCTD_DAY3_PREVIOUSLY_INSPECTED_DEVELOPMENT"
POLICY="CAMERA_QUALITY_SPLIT_V1_UNVERIFIED_FIRST_FRAME"


def create_trace(selection_csv: Path, clip_dir: Path, *,
                 environment: str="development") -> dict:
    if environment.strip().lower() not in {"development","local","test"}:
        raise ValueError("Protected mode denies private research analysis")
    if (selection_csv.is_symlink() or clip_dir.is_symlink()
        or not selection_csv.is_file() or not clip_dir.is_dir()
        or not clip_dir.is_absolute()):
        raise ValueError("Private source unavailable")
    private_root=clip_dir.resolve()
    if private_root==ROOT or ROOT in private_root.parents:
        raise ValueError("Private research cannot be analyzed inside checkout")
    if selection_csv.resolve().parent != private_root:
        raise ValueError("Use a pinned annotation sheet in the private clip folder")
    # Reuses existing full source-hash, annotation and MP4 checks.
    catalog=prepare(selection_csv,private_root)
    frozen_path=private_root/"kw-research-replay.local.json"
    if frozen_path.is_symlink() or not frozen_path.is_file() or frozen_path.stat().st_size>24_000:
        raise ValueError("Source replay manifest missing or unsafe")
    frozen=json.loads(frozen_path.read_text(encoding="utf-8"))
    if frozen!=catalog:
        raise ValueError("Source replay hashes or annotated intervals changed")
    if catalog["schema"]!="KW_RESEARCH_REPLAY_V1" or len(catalog["clips"])!=4:
        raise ValueError("Unexpected private research catalog")
    clips=[]
    for item in catalog["clips"]:
        path=private_root/item["filename"]
        if path.is_symlink():
            raise ValueError("Source symlink prohibited")
        cap=cv2.VideoCapture(str(path))
        if not cap.isOpened():
            raise ValueError("Private clip cannot be decoded")
        try:
            frames=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps=float(cap.get(cv2.CAP_PROP_FPS))
            if (frames<60 or frames>900 or not math.isfinite(fps)
                or abs(fps-3)>0.02 or abs(frames/fps-item["duration_seconds"])>1.5):
                raise ValueError("Inconsistent decoded source clock")
            base=None
            previous=None
            samples=[]
            index=0
            while True:
                okay,frame=cap.read()
                if not okay:break
                if base is None:base=frame.copy()
                if index%3==0:
                    # This is deliberately an unapproved first-frame comparison.
                    observation=sample(frame,reference=base,previous=previous)
                    triage=observation["evidence_triage"]
                    sec=round(index/fps,3)
                    active=(item["event_start_seconds"] is not None
                            and sec>=item["event_start_seconds"]
                            and sec<item["event_end_seconds"])
                    samples.append({
                        "second":sec,"frame0":index,"annotation_in_event":bool(active),
                        "usability":triage["usability"],
                        "interference_review":triage["interference_review"],
                        "reason":triage["usability_reason"],
                    })
                    previous=frame.copy()
                index+=1
            if abs(index-frames)>2 or not samples or len(samples)>300:
                raise ValueError("Incomplete or excessive video decode")
            clips.append({
                "id":item["id"],"source_sha256":item["source_sha256"],
                "duration_seconds":item["duration_seconds"],
                "frame_count":index,"fps":round(fps,3),
                "samples":samples,
                "counts":{
                    "evidence_unusable":sum(
                        x["usability"]=="NOT_USABLE_FOR_VISUAL_VERIFICATION"
                        for x in samples),
                    "possible_interference":sum(
                        x["interference_review"]=="POSSIBLE_SCENE_INTERFERENCE_REVIEW"
                        for x in samples),
                    "annotation_event_samples":sum(x["annotation_in_event"] for x in samples),
                },
            })
        finally:cap.release()
    return {
        "schema":SCHEMA, "source_collection":ORIGIN,"heuristic_policy":POLICY,
        "research_only":True, "independent_holdout":False,
        "training_centre_validation":False,
        "reference_source":"UNVERIFIED_FIRST_VIDEO_FRAME",
        "model_accuracy_qualified":False,
        "automatic_enforcement_authorized":False,
        "sampling":"ONE_FPS_SPARSE_LOCAL_DECODE",
        "clips":clips,
    }


def write_once(path: Path, receipt: dict) -> None:
    if path.is_symlink():
        raise ValueError("Refusing existing symlink output")
    dest=path.expanduser().resolve()
    if dest==ROOT or ROOT in dest.parents:
        raise ValueError("Never write private analysis under project root")
    dest.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(dest,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"w",encoding="utf-8") as stream:
        json.dump(receipt,stream,sort_keys=True,indent=2,allow_nan=False)
        stream.write("\n");stream.flush();os.fsync(stream.fileno())


def main() -> int:
    parser=argparse.ArgumentParser(description="Offline source-matched research cue trace")
    parser.add_argument("--clip-dir",type=Path,required=True)
    parser.add_argument("--selection-csv",type=Path)
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    folder=args.clip_dir.expanduser()
    csv= args.selection_csv or folder/"selected_clips.csv"
    output=args.output or folder/"kw-research-analysis.local.json"
    try:
        result=create_trace(csv,folder,environment=os.getenv("KAUSHALWATCH_ENV","development"))
        write_once(output,result)
    except (OSError,ValueError,KeyError,TypeError,cv2.error,json.JSONDecodeError):
        print(json.dumps({"schema":SCHEMA,"status":"BLOCKED_OR_NOT_PREPARED",
                          "field_accuracy_qualified":False}))
        return 2
    print(json.dumps({"schema":SCHEMA,"status":"DEVELOPMENT_ONLY",
                      "clips":len(result["clips"]),
                      "field_accuracy_qualified":False,
                      "media_exported":False}))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
