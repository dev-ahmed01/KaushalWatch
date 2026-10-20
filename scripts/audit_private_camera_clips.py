"""Audit approved *local* UHCTD development clips against current baseline assess_camera.

No Drive credentials, network, frame export, tuning or automatic enforcement.
The output is deliberately NOT a held-out field model-accuracy claim.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any

import cv2

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"backend"))
from app.services.camera_trust import assess_camera

SCHEMA="KW_PRIVATE_BASELINE_AUDIT_V1"
SHA=re.compile(r"[a-f0-9]{64}\Z")
# Frozen copied annotation offsets. (clip frame zero is original 0-based frame.)
# Deliberately no inference of these labels from a detector prediction.
SOURCES={
 "covered_gentle_frame721_onset.mp4":("covered",684,721),
 "covered_strong_frame162676_onset.mp4":("covered",162639,162676),
 "defocused_strong_frame166275_onset.mp4":("defocused",166238,166275),
 "moved_gentle_frame7919_onset.mp4":("moved",7882,7919),
 "normal_control_1.mp4":("normal",135,None),
 "normal_control_2.mp4":("normal",16151,None),
}
BLOCKED_ENVS={"pilot","production","prod","staging"}

def sha256_file(p:Path)->str:
    h=hashlib.sha256()
    with p.open("rb") as f:
        for block in iter(lambda:f.read(1<<20),b""):
            h.update(block)
    return h.hexdigest()

def validate_sources(cache:Path, manifest:dict, env:dict[str,str]) -> dict[str,str]:
    if env.get("KAUSHALWATCH_ENV","development").lower() in BLOCKED_ENVS:
        raise ValueError("Protected runtime cannot analyze development footage")
    if not cache.is_absolute() or cache.is_symlink() or not cache.is_dir():
        raise ValueError("Private cache must be a real absolute directory")
    root=cache.resolve()
    if root==ROOT or ROOT in root.parents:
        raise ValueError("Keep licensed research media outside Git checkout")
    if (not isinstance(manifest,dict)
        or manifest.get("schema")!="KW_PRIVATE_FOOTAGE_SELECTION_V1"
        or manifest.get("independent_holdout") is not False
        or manifest.get("training_centre_recording") is not False
        or manifest.get("public_distribution_authorized") is not False):
        raise ValueError("Unsupported or improperly qualified research source")
    files=manifest.get("shortlist")
    if not isinstance(files,list) or not 6<=len(files)<=50:
        raise ValueError("Missing private hash inventory")
    found:dict[str,str]={}
    for item in files:
        if not isinstance(item,dict):
            raise ValueError("Untrusted item")
        name=item.get("file")
        digest=item.get("sha256")
        if (not isinstance(name,str) or not isinstance(digest,str)
            or not SHA.fullmatch(digest) or not re.fullmatch(r"[a-z0-9_]+\.mp4",name)
            or name in found):
            raise ValueError("Unsafe or duplicate source")
        found[name]=digest
    if not SOURCES.keys()<=found.keys():
        raise ValueError("Required research set is incomplete")
    for name in SOURCES:
        p=root/name
        if p.is_symlink() or not p.is_file() or not 10000<=p.stat().st_size<=16_000_000:
            raise ValueError("Source missing or unsafe")
        if sha256_file(p)!=found[name]:
            raise ValueError("Source clip digest drift")
        with p.open("rb") as stream:
            if stream.read(16)[4:8]!=b"ftyp":
                raise ValueError("Not an MP4")
    return found

def score_clip(path:Path,label:str,start_frame0:int,event_start:int|None)->dict[str,Any]:
    cap=cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise ValueError("Clip decoder failed")
    count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps=float(cap.get(cv2.CAP_PROP_FPS))
    if not (60<=count<=500 and abs(fps-3)<=.02):
        cap.release()
        raise ValueError("Unexpected frame metadata")
    previous=reference=None
    pre=post=pre_bad=post_bad=0
    reasons={"pre":{"blur":0,"dark":0,"frozen":0,"shift":0},
             "event":{"blur":0,"dark":0,"frozen":0,"shift":0}}
    index=0
    try:
        while True:
            ok,frame=cap.read()
            if not ok:break
            if index==0:reference=frame.copy()
            if index%3==0:
                actual=start_frame0+index+1
                positive=event_start is not None and actual>=event_start
                region="event" if positive else "pre"
                result=assess_camera(frame,previous_frame=previous,reference_frame=reference)
                if positive:
                    post+=1;post_bad+=int(not result.trusted)
                else:
                    pre+=1;pre_bad+=int(not result.trusted)
                for field,val in (
                    ("blur",result.is_blurry),("dark",result.is_too_dark),
                    ("frozen",result.is_frozen),("shift",result.scene_shift)):
                    reasons[region][field]+=int(val)
                previous=frame.copy()
            index+=1
    finally:
        cap.release()
    if abs(index-count)>2:
        raise ValueError("Partial decode")
    return {
        "label":label,"decoded_frames":index,"fps":round(fps,3),"stride_frames":3,
        "pre_event_samples":pre,"pre_event_untrusted":pre_bad,
        "annotated_event_samples":post,"event_untrusted":post_bad,
        "reason_counts":reasons,"first_frame_reference_verified":False,
    }

def evaluate(cache:Path,manifest:dict, env:dict[str,str])->dict[str,Any]:
    found=validate_sources(cache,manifest,env)
    rows=[]
    for name,(label,first,onset) in SOURCES.items():
        row=score_clip(cache/name,label,first,onset)
        row.update({"source_alias":name,"source_sha256":found[name]})
        rows.append(row)
    first=sum(x["pre_event_samples"] for x in rows)
    first_bad=sum(x["pre_event_untrusted"] for x in rows)
    positive=sum(x["annotated_event_samples"] for x in rows)
    positive_bad=sum(x["event_untrusted"] for x in rows)
    return {
        "schema":SCHEMA,
        "source_is_previously_inspected_development_data":True,
        "independently_held_out":False,"institutional_training_accuracy":False,
        "physical_tamper_proven":False,"model_promoted":False,
        "analysis":"unmodified assess_camera defaults; per-clip first-frame reference; 1 FPS",
        "not_full_camera_worker_or_continuous_stream":True,
        "summary":{
            "clips":len(rows),"positive_event_samples":positive,
            "positive_event_samples_untrusted":positive_bad,
            "pre_event_and_normal_samples":first,
            "pre_event_and_normal_samples_untrusted":first_bad,
        },
        "per_clip":rows,
        "qualifications":"Development-only evidence-quality flags, NOT independent field precision, recall or tamper diagnosis.",
        "secrets_or_source_media_exported":False,
    }

def write_exclusive(path:Path, data:dict)->None:
    dest=path.expanduser()
    if dest.is_symlink():
        raise ValueError("Unsafe output")
    dest=dest.resolve()
    if dest==ROOT or ROOT in dest.parents:
        raise ValueError("Do not place private receipts in Git")
    dest.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(dest,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"w",encoding="utf-8") as f:
        json.dump(data,f,sort_keys=True,indent=2,allow_nan=False)
        f.write("\n");f.flush();os.fsync(f.fileno())

def main()->int:
    p=argparse.ArgumentParser(description="Local-only development clip audit (not field validation)")
    p.add_argument("--clip-dir",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    args=p.parse_args()
    try:
        cache=args.clip_dir.expanduser().resolve()
        # Check the directory path before resolving symbolic links.
        if args.clip_dir.expanduser().is_symlink():
            raise ValueError("Private cache symlink")
        manifest_path=cache/"private-source-manifest.json"
        if manifest_path.is_symlink() or not manifest_path.is_file() or manifest_path.stat().st_size>100_000:
            raise ValueError("Invalid private manifest")
        inventory=json.loads(manifest_path.read_text(encoding="utf-8"))
        report=evaluate(cache,inventory,dict(os.environ))
        write_exclusive(args.output,report)
    except (OSError,ValueError,KeyError,TypeError,json.JSONDecodeError):
        print(json.dumps({"schema":SCHEMA,"status":"BLOCKED_PRIVATE_INPUTS_INVALID",
                          "field_qualified":False}))
        return 2
    print(json.dumps({"schema":SCHEMA,"status":"DEVELOPMENT_AUDIT_ONLY",
                      "summary":report["summary"],"field_qualified":False}))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
