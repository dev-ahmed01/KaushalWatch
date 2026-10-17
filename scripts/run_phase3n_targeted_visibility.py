#!/usr/bin/env python3
"""Phase 3N bounded, no-media-export research sampling (not a full replay).

Read the already-completed Phase 3M numeric reports to prioritize ALL
annotated defocus intervals plus alternate camera-moved intervals. Sample
six explicitly fixed temporal positions around each event. Raw camera
signals are NOT rerun or changed. No sample image is ever written.
Outputs are numeric, not validated image usability, physical provenance,
or independent hold-out results.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
import math
from pathlib import Path
import sys

import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"backend"))
from app.services.camera_visibility_quality_shadow import VisibilityQualityShadow  # noqa: E402
from run_phase3m_dual_day_research import (  # noqa: E402
    _read_source, _choose_reference_index, _frame_in_memory, _memory_sha, _write_json,
)

KINDS={0:"normal",1:"covered",2:"defocused",3:"moved"}
STAGES=("before_start","onset","after_onset_30","event_end","after_end_30","after_end_120")


def _labels_and_events(labels:Path, frames:int) -> tuple[np.ndarray,list[dict]]:
    values=np.empty(frames,dtype=np.uint8)
    events=[]
    ongoing=None
    with Path(labels).open(newline="",encoding="utf-8-sig") as fd:
        rows=csv.reader(fd,strict=True)
        for pos in range(frames):
            row=next(rows,None)
            if row is None or len(row)<5:
                raise ValueError(f"Annotation missing at frame {pos+1}")
            try:
                n=int(row[0]); kind=int(row[1])
            except (ValueError,TypeError) as exc:
                raise ValueError(f"Invalid annotation at frame {pos+1}") from exc
            if n!=pos+1 or kind not in KINDS:
                raise ValueError(f"Noncontinuous annotation at frame {pos+1}")
            values[pos]=kind
            if ongoing is not None and ongoing["kind"]!=kind:
                ongoing["end_frame"]=pos
                events.append(ongoing)
                ongoing=None
            if ongoing is None and kind!=0:
                ongoing={"kind":kind,"start_frame":pos+1,"end_frame":None}
        if next(rows,None) is not None:
            raise ValueError("Extra label rows beyond video")
    if ongoing is not None:
        ongoing["end_frame"]=frames
        events.append(ongoing)
    return values,events


def _target_frames(events:list[dict], *, fps:float, total:int)->list[dict]:
    def frame_at(event,offset):
        return max(1,min(total,event+round(offset*fps)))
    chosen=[]
    moved_count=0
    for event in events:
        if event["kind"]==2:
            include=True
        elif event["kind"]==3:
            include=moved_count%2==0
            moved_count+=1
        else:
            include=False
        if not include:
            continue
        start=end=None
        start=event["start_frame"]
        end=event["end_frame"]
        times=(
            frame_at(start,-30),
            start,
            frame_at(start,30),
            end,
            frame_at(end,30),
            frame_at(end,120),
        )
        for stage,frame in zip(STAGES,times):
            chosen.append({
                "target_event_class":KINDS[event["kind"]],
                "target_event_start_frame":start,
                "target_event_end_frame":end,
                "stage":stage,
                "sample_frame":frame,
            })
    return chosen


def _read_exact_frame(cap,frame_number:int,expected_shape:tuple[int,int])->np.ndarray:
    if not cap.set(cv2.CAP_PROP_POS_FRAMES,frame_number-1):
        raise ValueError("Video decoder cannot seek to selected frame")
    ok,frame=cap.read()
    if not ok or frame is None:
        raise ValueError(f"Unable to decode target frame {frame_number}")
    next_number=cap.get(cv2.CAP_PROP_POS_FRAMES)
    if (not math.isfinite(next_number) or abs(next_number-frame_number)>0.51):
        raise ValueError("Decoder position inconsistent with selected frame")
    if frame.dtype!=np.uint8 or frame.shape!=(expected_shape[0],expected_shape[1],3):
        raise ValueError("Decoded source dimensions differ from pinned recording")
    return frame


def analyze_day(*,video:Path,annotations:Path,report_path:Path)->dict:
    stored=json.loads(Path(report_path).read_text(encoding="utf-8"))
    if (stored.get("status")!="FULL_DEVELOPMENT_CAUSE_REPLAY_UNAPPROVED_REFERENCE_NOT_HELD_OUT"
            or stored.get("production_qualified") is not False
            or stored.get("production_integration") is not False
            or stored.get("evaluated_frames")!=stored.get("total_frames")):
        raise ValueError("A completed, unqualified Phase3M source report is required")
    info=_read_source(video,annotations)
    for left,right in (
        ("video_sha256","video_sha256"),
        ("annotations_sha256","annotations_sha256"),
        ("total_frames","frames"),
    ):
        if stored.get(left)!=info[right]:
            raise ValueError("Source report differs from pinned local recording: "+left)
    frame_num,decision=_choose_reference_index(
        annotations,fps=info["fps"],frames=info["frames"],
    )
    if frame_num!=stored.get("in_memory_development_reference_source_frame"):
        raise ValueError("Unapproved reference selection changed from Phase3M")
    reference=_frame_in_memory(video,frame_number=frame_num,expected=info)
    if _memory_sha(reference)!=stored.get("in_memory_development_reference_pixel_sha256"):
        raise ValueError("In-memory research reference digest mismatch")
    analyzer=VisibilityQualityShadow.from_bgr(reference)
    labels,events=_labels_and_events(annotations,info["frames"])
    expected_events=stored.get("annotated_event_counts",{})
    actual_counts=Counter(KINDS[e["kind"]] for e in events)
    for name in ("covered","defocused","moved"):
        if actual_counts[name]!=expected_events.get(name,0):
            raise ValueError("Annotation event counts differ from completed report")
    targets=_target_frames(events,fps=info["fps"],total=info["frames"])
    baseline=stored["counterfactual_scene_gate_comparison"]["candidate_comparisons"]["frozen_baseline"]
    seen=Counter()
    stage_signals={}
    individual=[]
    cap=cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise ValueError("Cannot open source decoder")
    try:
        for target in targets:
            item=_read_exact_frame(
                cap,target["sample_frame"],(info["height"],info["width"]),
            )
            result=analyzer.inspect(item)
            kind=KINDS[int(labels[target["sample_frame"]-1])]
            group=target["target_event_class"]+":"+target["stage"]+":"+kind
            seen[group]+=1
            stage_signals.setdefault(group,Counter())[result["quality_hypothesis"]]+=1
            base_event=baseline["events"][target["target_event_class"]]
            start=target["target_event_start_frame"]
            individual.append({
                **target,
                "actual_annotation_class_at_sample":kind,
                "quality_hypothesis":result["quality_hypothesis"],
                "relative_sharpness":result["relative_sharpness"],
                "relative_edge_fraction":result["relative_edge_fraction"],
                "relative_contrast":result["relative_contrast"],
                "baseline_event_fresh_review":start in base_event["fresh_event_start_frames"],
                "baseline_event_any_review":start in base_event["any_review_event_start_frames"],
            })
    finally:
        cap.release()
    return {
        "status":"PHASE3N_TARGETED_UNAPPROVED_REFERENCE_DEVELOPMENT_ONLY",
        "production_qualified":False,
        "source_is_held_out":False,
        "physical_reference_verified":False,
        "complete_video_replayed":False,
        "same_unnapproved_in_video_reference_as_phase3m":True,
        "video_sha256":info["video_sha256"],
        "annotations_sha256":info["annotations_sha256"],
        "reference_pixel_sha256":_memory_sha(reference),
        "source_frames_checked_against_phase3m":info["frames"],
        "event_counts_checked_against_phase3m":dict(actual_counts),
        "sampled_target_frames":len(targets),
        "sampled_positions":individual,
        "quality_hypothesis_by_event_phase_and_sample_class":{
            key:dict(counts) for key,counts in stage_signals.items()
        },
        "not_production_integrated":True,
        "frames_images_or_crops_exported":False,
        "limitations":[
            "Annotation-normal reference is not independently healthy or approved",
            "Uncalibrated sharpness can be affected by image texture/illumination/noise/codec",
            "Camera event labels are not independent visual quality ground truth",
            "Sparse seek-based samples cannot reproduce continuous incident warning or recovery timelines",
            "Report event review status comes from prior full replay; sample quality does not overwrite it",
            "No thresholds selected and no automatic incident or reference recovery",
        ],
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for d in ("day3","day4"):
        p.add_argument(f"--{d}-video",required=True,type=Path)
        p.add_argument(f"--{d}-annotations",required=True,type=Path)
        p.add_argument(f"--{d}-report",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    p.add_argument("--allow-unapproved-development-reference",action="store_true")
    args=p.parse_args()
    if not args.allow_unapproved_development_reference:
        p.error("Must explicitly opt in to unapproved development reference")
    if args.out.suffix.lower()!=".json" or args.out.exists():
        p.error("New, unused output JSON path required")
    results={}
    for name in ("day3","day4"):
        print(name+": targeted sharpness and event-window analysis",flush=True)
        results[name]=analyze_day(
            video=getattr(args,name+"_video"),
            annotations=getattr(args,name+"_annotations"),
            report_path=getattr(args,name+"_report"),
        )
    result={
        "status":"PHASE3N_TWO_DAY_TARGETED_VISIBILITY_NOT_HELD_OUT",
        "production_qualified":False,
        "automatic_recovery_or_reference_reset":False,
        "full_day_repeated":False,
        "media_exported":False,
        "days":results,
    }
    _write_json(args.out,result)
    print(json.dumps({
        "status":result["status"],
        "samples_per_day":{k:v["sampled_target_frames"] for k,v in results.items()},
        "report":str(args.out.resolve()),
        "production_qualified":False,
    },indent=2))


if __name__=="__main__":
    main()
