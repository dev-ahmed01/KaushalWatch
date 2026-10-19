"""Prepare a private equipment-video replay from an existing saved GroundingDINO run.

Reads one existing source and receipt; makes no copies, uploads, downloads
or inference. This is operator attestation, not independent accuracy proof.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys

import cv2

def sha(path: Path)->str:
    digest=hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda:stream.read(1024*1024),b""):
            digest.update(part)
    return digest.hexdigest()

def build(root:Path,source_origin:str,license_basis:str,privacy_basis:str,
          roi:list[float],roi_basis:str)->dict:
    root=root.expanduser().resolve(strict=True)
    if not root.is_dir():raise ValueError("Private replay directory missing")
    for description in (source_origin,license_basis,privacy_basis,roi_basis):
        if not isinstance(description,str) or not 8<=len(description.strip())<=200:
            raise ValueError("Source custody description is missing or too long")
    if len(roi)!=4 or any(not math.isfinite(v) for v in roi):
        raise ValueError("Invalid reviewed camera region")
    x,y,w,h=roi
    if x<0 or y<0 or w<=0 or h<=0 or x+w>1 or y+h>1:
        raise ValueError("Camera-specific normalized ROI outside source")
    recording=root/"equipment.mp4"
    saved=root/"live-proposals.json"
    for part in (recording,saved):
        if part.is_symlink() or not part.is_file() or part.stat().st_size<20:
            raise ValueError("Local source or model receipt missing")
    if not 10_000<=recording.stat().st_size<=130_000_000:
        raise ValueError("Unsupported local recording size")
    if saved.stat().st_size>700_000:raise ValueError("Saved result too large")
    with recording.open("rb") as stream:
        if stream.read(12)[4:8]!=b"ftyp":raise ValueError("Expected approved MP4 video")
    source_hash=sha(recording)
    receipt=json.loads(saved.read_text(encoding="utf-8"))
    if (not isinstance(receipt,dict)
        or receipt.get("status")!="live_unreviewed_equipment_proposals"
        or receipt.get("source_video_sha256")!=source_hash
        or receipt.get("model_inference_executed") is not True
        or receipt.get("qualified") is not False):
        raise ValueError("Model receipt has no matched source/proposal status")
    capture=cv2.VideoCapture(str(recording))
    try:
        if not capture.isOpened():raise ValueError("MP4 cannot be decoded")
        width=int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height=int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps=float(capture.get(cv2.CAP_PROP_FPS))
        frame_count=int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        if not 0.75<=width/height<=2.5 if height else True:
            raise ValueError("Unsupported video aspect ratio")
        if not 32<=width<=4096 or not 32<=height<=4096:
            raise ValueError("Video dimensions unavailable")
        if not math.isfinite(fps) or fps<=0 or frame_count<=0:
            raise ValueError("Video frame timing unavailable")
        duration=frame_count/fps
        if not 0.3<=duration<=360:raise ValueError("Invalid video duration")
    finally:
        capture.release()
    if not isinstance(receipt.get("proposal_rows"),list) or not 1<=len(receipt["proposal_rows"])<=48:
        raise ValueError("Missing real model samples")
    seconds=[r.get("second") if isinstance(r,dict) else None for r in receipt["proposal_rows"]]
    if any(type(v) not in (int,float) or not math.isfinite(v) or v<0 or v>=duration for v in seconds):
        raise ValueError("Model timestamp outside decoded recording")
    if sorted(seconds)!=seconds or len(set(seconds))!=len(seconds):
        raise ValueError("Timestamps must be unique and increasing")
    return {
        "schema":"KW_EQUIPMENT_REPLAY_ADMISSION_V1",
        "video_filename":"equipment.mp4",
        "receipt_filename":"live-proposals.json",
        "video_sha256":source_hash,"receipt_sha256":sha(saved),
        "source_origin":source_origin,"license_basis":license_basis,
        "privacy_basis":privacy_basis,"width":width,"height":height,
        "duration_seconds":round(duration,6),
        "roi":{"x":x,"y":y,"width":w,"height":h},
        "roi_basis":roi_basis
    }

def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dir",required=True,type=Path)
    p.add_argument("--source-origin",required=True)
    p.add_argument("--license-basis",required=True)
    p.add_argument("--privacy-basis",required=True)
    p.add_argument("--roi",required=True,nargs=4,type=float,metavar=("X","Y","WIDTH","HEIGHT"))
    p.add_argument("--roi-basis",required=True)
    options=p.parse_args()
    try:
        doc=build(options.dir,options.source_origin,options.license_basis,
                  options.privacy_basis,options.roi,options.roi_basis)
        target=options.dir.expanduser().resolve()/"equipment-replay.local.json"
        if target.exists() or target.is_symlink():raise ValueError("Refusing to overwrite private metadata")
        payload=(json.dumps(doc,indent=2,sort_keys=True)+"\n").encode()
        fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,"wb") as stream:stream.write(payload)
        print(json.dumps({"status":"private_equipment_source_admitted",
                          "copy_count":0,"upload_count":0,
                          "equipment_model_accuracy_qualified":False,
                          "independent_execution_verified":False}))
        return 0
    except (OSError,ValueError,TypeError,KeyError,json.JSONDecodeError):
        print(json.dumps({"status":"private_equipment_admission_blocked",
                          "copy_count":0,"upload_count":0,
                          "equipment_model_accuracy_qualified":False}))
        return 2

if __name__=="__main__":
    sys.exit(main())
