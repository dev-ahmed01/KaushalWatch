#!/usr/bin/env python3
"""One-command private local Day3+Day4 development experiment (NOT a release).

Requires an explicit --allow-unapproved-self-reference-development opt-in.
The reference frame is extracted into memory from the FIRST >=90 second
uninterrupted annotation-normal interval, subject to a 10-minute search
limit. No image pixels, frames, faces, cropped views, or video are written.
An annotation of NORMAL does NOT prove a healthy or safe scene. Neither
reference is independently approved, authenticated or production suitable.

Preflights and hashes BOTH local recordings/labels BEFORE processing.
Runs both 60-second previews, and optionally both COMPLETE recordings,
then the strict two-day Phase3L counterfactual comparison. No calibration
or choice of production policy occurs here. Every report is unqualified.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time

import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"backend"))

from app.services.camera_reference_offline_benchmark import sha256  # noqa: E402
from run_phase3k_local_forensics import replay  # noqa: E402
from compare_phase3l_dual_day import compare  # noqa: E402

DAY_NAMES=("day3","day4")
REFERENCE_MIN_NORMAL_SECONDS=90
REFERENCE_SEARCH_LIMIT_SECONDS=600


def _read_source(video:Path, labels:Path) -> dict:
    video,labels=Path(video),Path(labels)
    if not video.is_file() or not labels.is_file():
        raise ValueError("Both original video and original annotations must exist")
    cap=cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise ValueError("Unable to open original recording")
    try:
        fps=float(cap.get(cv2.CAP_PROP_FPS))
        frames=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if (not math.isfinite(fps) or fps<=0 or frames<=0):
            raise ValueError("Video FPS/frame count invalid")
        width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if not (32<=width<=1920 and 32<=height<=1080):
            raise ValueError("Unexpected source video dimensions")
    finally:
        cap.release()
    # File hashes also function as a run-specific no-overwrite evidence key.
    return {"video_sha256":sha256(video),"annotations_sha256":sha256(labels),
            "fps":fps,"frames":frames,"width":width,"height":height}


def _choose_reference_index(labels:Path, *, fps:float, frames:int) -> tuple[int,dict]:
    """Choose one fixed, explicit sampling protocol, no score optimization."""
    needed=math.ceil(fps*REFERENCE_MIN_NORMAL_SECONDS)
    scan=min(frames,math.ceil(fps*REFERENCE_SEARCH_LIMIT_SECONDS))
    first=0
    length=0
    selected=None
    with Path(labels).open(newline="",encoding="utf-8-sig") as stream:
        for n,row in enumerate(csv.reader(stream,strict=True),1):
            if n>scan:
                break
            if len(row)<5:
                raise ValueError(f"Missing reference-selection label at frame {n}")
            try:
                frame=int(row[0]); kind=int(row[1])
            except (ValueError,TypeError) as exc:
                raise ValueError(f"Invalid label at frame {n}") from exc
            if frame!=n or kind not in (0,1,2,3):
                raise ValueError(f"Noncontinuous/invalid annotation at frame {n}")
            if kind==0:
                if length==0:
                    first=n
                length+=1
                if length>=needed:
                    selected=first+(needed//2)
                    break
            else:
                length=0
    if selected is None:
        raise ValueError("No 90-second annotation-normal interval within first 10 minutes")
    return selected,{
        "selection_rule":"FIRST_90_SECONDS_CONSECUTIVE_ANNOTATION_NORMAL_MIDPOINT",
        "source_frame_1based":selected,
        "source_video_seconds":round((selected-1)/fps,4),
        "reference_verified_healthy":False,
        "reference_independently_reviewed":False,
        "reference_source_authenticated":False,
        "allowed_for_production":False,
    }


def _frame_in_memory(video:Path, *, frame_number:int, expected:dict) -> np.ndarray:
    cap=cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise ValueError("Source frame decoder cannot be opened")
    try:
        if frame_number>expected["frames"]:
            raise ValueError("Reference frame outside source recording")
        # Sequential grab is intentional; avoids unreliable random seeks at
        # keyframe boundaries on legacy UHCTD AVI codecs.
        for pos in range(1,frame_number+1):
            if not cap.grab():
                raise ValueError(f"Early video decode while selecting reference: {pos}")
        ok,frame=cap.retrieve()
        if not ok or frame is None or frame.dtype!=np.uint8:
            raise ValueError("Reference frame could not be decoded")
        if frame.shape!=(expected["height"],expected["width"],3):
            raise ValueError("Selected frame dimensions disagree with source header")
        return np.ascontiguousarray(frame)
    finally:
        cap.release()


def _memory_sha(frame:np.ndarray)->str:
    return hashlib.sha256(
        str(frame.shape).encode("ascii")+np.ascontiguousarray(frame).tobytes()
    ).hexdigest()


def _write_json(path:Path, document:dict)->None:
    if path.exists():
        raise FileExistsError("Refusing to overwrite prior results")
    path.parent.mkdir(parents=True,exist_ok=True)
    # Only small numeric JSON reports are materialized. If interrupted before
    # replace, the temporary report is not mistaken for final evidence.
    pending=path.with_suffix(".pending")
    if pending.exists():
        raise FileExistsError("Incomplete pending report already exists")
    with pending.open("x",encoding="utf-8") as out:
        json.dump(document,out,indent=2,sort_keys=True)
        out.write("\n")
    os.replace(pending,path)


def run_pair(*, day3_video:Path,day3_annotations:Path,
             day4_video:Path,day4_annotations:Path,run_dir:Path,
             sample_seconds:float=1.0,run_full:bool=False,
             preview_seconds:float=60.0) -> dict:
    if (not isinstance(sample_seconds,(float,int)) or not math.isfinite(sample_seconds)
            or sample_seconds<=0 or not isinstance(preview_seconds,(float,int))
            or not math.isfinite(preview_seconds) or preview_seconds<=0):
        raise ValueError("Positive sample cadence and preview seconds required")
    if Path(run_dir).exists():
        raise FileExistsError("Run directory exists; use a new immutable run path")
    sources={
        "day3":(Path(day3_video),Path(day3_annotations)),
        "day4":(Path(day4_video),Path(day4_annotations)),
    }
    # Fail before writing ANY output if both datasets are not valid, unique,
    # or unable to provide a fixed early annotation-normal reference frame.
    manifests={}
    references={}
    for day,(video,labels) in sources.items():
        info=_read_source(video,labels)
        selected,decision=_choose_reference_index(
            labels,fps=info["fps"],frames=info["frames"],
        )
        references[day]=_frame_in_memory(
            video,frame_number=selected,expected=info,
        )
        manifests[day]={**info,**decision,
                        "reference_pixel_sha256":_memory_sha(references[day])}
    if manifests["day3"]["video_sha256"]==manifests["day4"]["video_sha256"]:
        raise ValueError("Both days point to identical video content")
    # Deliberately do not write local paths into exported evidence.
    Path(run_dir).mkdir(parents=True,exist_ok=False)
    _write_json(Path(run_dir)/"research_reference_manifest.json",{
        "status":"TWO_UNAPPROVED_INVIDEO_REFERENCES_DEVELOPMENT_ONLY",
        "reference_selection_rule_fixed_before_analysis":True,
        "source_paths_embedded":False,
        "reference_media_exported":False,
        "days":manifests,
        "source_provenance_independently_confirmed":False,
        "reference_health_independently_confirmed":False,
        "production_qualified":False,
    })
    for day,(video,labels) in sources.items():
        ref=references[day]
        info=manifests[day]
        print(f"{day}: preview, self-sourced unapproved fixed reference at {info['source_video_seconds']}s",flush=True)
        preview=replay(
            video=video,annotations=labels,reference=None,
            video_sha256=info["video_sha256"],
            annotations_sha256=info["annotations_sha256"],
            reference_sha256=info["reference_pixel_sha256"],
            in_memory_research_frame=ref,
            in_memory_frame_number=info["source_frame_1based"],
            sample_seconds=sample_seconds,preview_seconds=preview_seconds,
        )
        if preview["status"]!="PREVIEW_DEVELOPMENT_CAUSE_REPLAY_NOT_HELD_OUT":
            raise RuntimeError("Preview unexpectedly consumed complete recording")
        _write_json(Path(run_dir)/"preview"/f"{day}.json",preview)
    if not run_full:
        summary={
            "status":"PHASE3M_PREVIEWS_ONLY_NO_FULL_RECORDING_EVALUATION",
            "day3_video_sha256":manifests["day3"]["video_sha256"],
            "day4_video_sha256":manifests["day4"]["video_sha256"],
            "full_recording_comparison":False,"production_qualified":False,
            "next_step":"Use new run directory and --run-full to replay both complete sources",
        }
        _write_json(Path(run_dir)/"phase3m_status.json",summary)
        return summary
    del references
    # Reuse manifest but reload in-memory image from same pinned source before
    # each COMPLETE replay. The full video is hashed again by replay().
    for day,(video,labels) in sources.items():
        info=manifests[day]
        reference=_frame_in_memory(
            video,frame_number=info["source_frame_1based"],expected=info,
        )
        if _memory_sha(reference)!=info["reference_pixel_sha256"]:
            raise ValueError("Unapproved fixed reference bytes changed since preflight")
        print(f"{day}: complete full-day replay; no production authorization",flush=True)
        report=replay(
            video=video,annotations=labels,reference=None,
            video_sha256=info["video_sha256"],
            annotations_sha256=info["annotations_sha256"],
            reference_sha256=info["reference_pixel_sha256"],
            in_memory_research_frame=reference,
            in_memory_frame_number=info["source_frame_1based"],
            sample_seconds=sample_seconds,
        )
        if report["status"]!="FULL_DEVELOPMENT_CAUSE_REPLAY_UNAPPROVED_REFERENCE_NOT_HELD_OUT":
            raise RuntimeError("Unexpectedly incomplete full recording")
        _write_json(Path(run_dir)/"full"/f"{day}.json",report)
        del reference
    dual=compare(
        Path(run_dir)/"full"/"day3.json",
        Path(run_dir)/"full"/"day4.json",
    )
    _write_json(Path(run_dir)/"phase3m_dual_day_comparison.json",dual)
    result={
        "status":"PHASE3M_FULL_DUAL_DAY_DEVELOPMENT_REPLAY_COMPLETE_NOT_HELD_OUT",
        "production_qualified":False,
        "reference_independently_approved":False,
        "source_frames_checked":{
            day:manifests[day]["frames"] for day in DAY_NAMES
        },
        "candidate_results":{
            name:details["status"]
            for name,details in dual["candidate_results"].items()
        },
        "no_automatic_candidate_selection":True,
        "output_files":[
            "research_reference_manifest.json",
            "full/day3.json","full/day4.json","phase3m_dual_day_comparison.json",
        ],
    }
    _write_json(Path(run_dir)/"phase3m_status.json",result)
    return result


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__)
    for day in DAY_NAMES:
        p.add_argument(f"--{day}-video",type=Path,required=True)
        p.add_argument(f"--{day}-annotations",type=Path,required=True)
    p.add_argument("--run-dir",type=Path,required=True)
    p.add_argument("--sample-seconds",type=float,default=1.0)
    p.add_argument("--preview-seconds",type=float,default=60.0)
    p.add_argument("--run-full",action="store_true")
    p.add_argument("--allow-unapproved-self-reference-development",action="store_true")
    args=p.parse_args()
    if not args.allow_unapproved_self_reference_development:
        p.error("Explicit consent to UNAPPROVED in-video research references is required")
    t=time.monotonic()
    result=run_pair(
        day3_video=args.day3_video,day3_annotations=args.day3_annotations,
        day4_video=args.day4_video,day4_annotations=args.day4_annotations,
        run_dir=args.run_dir,sample_seconds=args.sample_seconds,
        preview_seconds=args.preview_seconds,run_full=args.run_full,
    )
    result["elapsed_seconds"]=round(time.monotonic()-t,2)
    print(json.dumps(result,indent=2))


if __name__=="__main__":
    main()
