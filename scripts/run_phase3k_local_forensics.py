#!/usr/bin/env python3
"""LOCAL DEVELOPMENT FORENSICS ONLY. NO APPROVED REFERENCE OR LIVE CAMERA.

An explicitly provided, SHA-pinned local reference frame is used for a
read-only dataset comparison. This does not verify that the frame came from
the correct physical camera, has been independently reviewed, or has
legal consent to use. Does not call production app or protected S3.
Numeric aggregate JSON only, no image export, no camera/enforcement effects.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"backend"))

from app.services.camera_reference_offline_benchmark import sha256  # noqa: E402
from app.services.camera_shadow_fusion import ShadowFusionProbe  # noqa: E402
from app.services.camera_spatial_scene_shadow import SpatialSceneShadow, _small  # noqa: E402
from app.services.camera_persistent_scene_probe import PersistentSceneProbe, _gray_small  # noqa: E402
from app.services.camera_scene_cause_shadow import SceneCauseDiagnostics  # noqa: E402
from app.services.camera_counterfactual_shadow import OfflineCandidateComparison  # noqa: E402
from app.services.camera_incident_continuity_shadow import IncidentContinuityShadow  # noqa: E402

CLASSES={0:"normal",1:"covered",2:"defocused",3:"moved"}


def valid_sha(value: str) -> bool:
    return isinstance(value,str) and len(value)==64 and all(x in "0123456789abcdef" for x in value)


def replay(*,video:Path, annotations:Path, reference:Path|None,
           video_sha256:str, annotations_sha256:str, reference_sha256:str,
           sample_seconds:float=1.0, preview_seconds:float|None=None,
           in_memory_research_frame:np.ndarray|None=None,
           in_memory_frame_number:int|None=None) -> dict:
    if (not isinstance(sample_seconds,(float,int)) or isinstance(sample_seconds,bool)
        or not math.isfinite(sample_seconds) or sample_seconds<=0 or
        (preview_seconds is not None and (
            not isinstance(preview_seconds,(float,int)) or
            not math.isfinite(preview_seconds) or preview_seconds<=0))):
        raise ValueError("Positive finite sample/preview seconds required")
    research_mode=in_memory_research_frame is not None
    if (research_mode and reference is not None) or (not research_mode and reference is None):
        raise ValueError("Choose exactly one explicit reference source")
    if research_mode and (
        type(in_memory_frame_number) is not int or in_memory_frame_number<1
    ):
        raise ValueError("Source frame number required for unapproved development reference")
    paths=(Path(video),Path(annotations))
    digests=(video_sha256,annotations_sha256,reference_sha256)
    if not all(p.is_file() for p in paths):
        raise ValueError("Video and annotations must exist")
    if not research_mode and not Path(reference).is_file():
        raise ValueError("Explicit local reference image must exist")
    if not all(valid_sha(d) for d in digests):
        raise ValueError("All three explicit SHA-256 hashes are required")
    for path,expected in zip(paths,(video_sha256,annotations_sha256)):
        if sha256(path)!=expected:
            raise ValueError("Source digest mismatch: no video decoded")
    if research_mode:
        original=np.ascontiguousarray(in_memory_research_frame).copy()
        encoded_source_digest=hashlib.sha256(
            str(original.shape).encode("ascii")+original.tobytes()
        ).hexdigest()
        if encoded_source_digest!=reference_sha256:
            raise ValueError("Unapproved in-memory reference pixel digest mismatch")
    else:
        if sha256(Path(reference))!=reference_sha256:
            raise ValueError("Source digest mismatch: no video decoded")
        original=cv2.imread(str(reference),cv2.IMREAD_COLOR)
    if (original is None or original.ndim!=3 or original.dtype!=np.uint8
            or original.shape[2]!=3 or
            original.shape[0]>1080 or original.shape[1]>1920
            or min(original.shape[:2])<32):
        raise ValueError("Invalid or excessive reference frame dimensions")
    reference_small=_small(original)
    spatial=SpatialSceneShadow(temporary_reference=reference_small.copy())
    persistent=PersistentSceneProbe(temporary_reference=_gray_small(original).copy())
    probe=ShadowFusionProbe(spatial=spatial,persistent=persistent)
    cause=SceneCauseDiagnostics(reference_small)

    cap=cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise ValueError("Video cannot be opened")
    totals=Counter(); reviews=Counter(); unknowns=Counter()
    onset_events=Counter(); fresh_events=Counter(); preexisting=Counter()
    causes={name:Counter() for name in CLASSES.values()}
    causes_on_review={name:Counter() for name in CLASSES.values()}
    inspections=Counter()
    normal_seconds=0.0; new_normal_episodes=0
    prev_cls=None; prev_review=False; active_event=None; sample_count=0
    try:
        fps=float(cap.get(cv2.CAP_PROP_FPS))
        length=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if not math.isfinite(fps) or fps<=0 or length<=0:
            raise ValueError("Video must report valid FPS and frames")
        step=max(1,round(sample_seconds*fps)); effective=step/fps
        counterfactual=OfflineCandidateComparison(fps)
        continuity=IncidentContinuityShadow(clear_seconds=60.0)
        limit=length if preview_seconds is None else min(length,math.ceil(preview_seconds*fps))
        with annotations.open(newline="",encoding="utf-8-sig") as file:
            source=csv.reader(file,strict=True)
            for index in range(limit):
                label=next(source,None)
                if label is None or len(label)<5:
                    raise ValueError(f"Annotation missing at {index+1}")
                try:
                    sequence=int(label[0]); kind=int(label[1])
                except (ValueError,TypeError) as exc:
                    raise ValueError(f"Invalid annotation at {index+1}") from exc
                if sequence!=index+1 or kind not in CLASSES:
                    raise ValueError(f"Frame index/class mismatch at {index+1}")
                if kind!=prev_cls:
                    if kind>0:
                        onset_events[CLASSES[kind]]+=1
                        active_event={"kind":kind,"preexisting":prev_review,"fresh":False}
                        if prev_review:
                            preexisting[CLASSES[kind]]+=1
                    else:
                        active_event=None
                    prev_cls=kind
                counterfactual.annotation(index+1,kind)
                if kind==0:
                    normal_seconds+=1/fps
                if not cap.grab():
                    raise ValueError(f"Early video end at frame {index+1}")
                if index%step:
                    continue
                success,frame=cap.retrieve()
                if not success or frame is None:
                    raise ValueError(f"Cannot decode frame {index+1}")
                result=probe.observe(frame,effective)
                if result["decision"]=="WARMUP":
                    raise ValueError("Reference auto warmup is not allowed")
                name=CLASSES[kind]; review=result["review_cue"]
                totals[name]+=1
                if result["evidence_status"]=="UNKNOWN_LOW_TEXTURE":
                    unknowns[name]+=1
                if review:
                    reviews[name]+=1
                    if kind==0 and not prev_review:
                        new_normal_episodes+=1
                    if kind>0 and active_event and not active_event["preexisting"] and not active_event["fresh"] and not prev_review:
                        fresh_events[name]+=1
                        active_event["fresh"]=True
                # Evaluate every candidate on the same complete per-sample
                # diagnostic evidence. Only JSON forensic *counts* are
                # accumulated every fifth sample to limit report size.
                measure=cause.inspect(frame,spatial_evidence_status=result["evidence_status"])
                counterfactual.observation(
                    index+1,kind,raw_review=review,
                    evidence_status=result["evidence_status"],
                    cause=measure,sample_seconds=effective,
                )
                continuity.observe(
                    annotation_class=kind,raw_review=review,
                    spatial_evidence_status=result["evidence_status"],
                    sample_seconds=effective,
                )
                if sample_count%5==0:
                    inspections[name]+=1
                    causes[name].update(measure["hypotheses"])
                    if review:
                        causes_on_review[name].update(measure["hypotheses"])
                prev_review=review
                sample_count+=1
            if limit==length and next(source,None) is not None:
                raise ValueError("Annotations have additional rows beyond video")
    finally:
        cap.release()
    comparison=counterfactual.result(full=(limit==length))
    frozen=comparison["candidate_comparisons"]["frozen_baseline"]
    if (frozen["review_samples_by_class"]!=dict(reviews)
            or frozen["sampled_by_class"]!=dict(totals)
            or frozen["normal_review_episodes_per_normal_hour"]!=(
                round(new_normal_episodes/(normal_seconds/3600),6)
                if normal_seconds else None)
            or any(frozen["events"][name]["fresh_review_events"]!=fresh_events[name]
                   for name in ("covered","defocused","moved"))):
        raise RuntimeError("Candidate frozen baseline disagrees with original raw replay accounting")
    return {
        "sampled_warning_incident_continuity_diagnostic":continuity.summary(),
        "counterfactual_scene_gate_comparison": comparison,
        "status":("FULL_DEVELOPMENT_CAUSE_REPLAY_UNAPPROVED_REFERENCE_NOT_HELD_OUT"
                  if limit==length else "PREVIEW_DEVELOPMENT_CAUSE_REPLAY_NOT_HELD_OUT"),
        "reference_origin_independently_verified":False,
        "source_is_held_out":False,
        "production_qualified":False,
        "production_integration":False,
        "automatic_reference_reset":False,
        "raw_camera_review_fraction_by_class":{
            name:(round(reviews[name]/totals[name],6) if totals[name] else None)
            for name in CLASSES.values()
        },
        "raw_review_samples_by_class":dict(reviews),
        "sampled_samples_by_class":dict(totals),
        "low_texture_unknown_samples_by_class":dict(unknowns),
        "annotated_event_counts":dict(onset_events),
        "fresh_event_review_counts":dict(fresh_events),
        "events_preexisting_review":dict(preexisting),
        "new_normal_review_episodes_per_normal_hour":(
            round(new_normal_episodes/(normal_seconds/3600),6) if normal_seconds else None
        ),
        "cause_diagnostic_sample_stride":5,
        "cause_inspections_by_class":dict(inspections),
        "cause_hypotheses_by_class":{k:dict(v) for k,v in causes.items()},
        "cause_hypotheses_during_raw_review":{k:dict(v) for k,v in causes_on_review.items()},
        "evaluated_frames":limit,"total_frames":length,
        "fps":fps,"effective_sample_seconds":effective,
        "video_sha256":digests[0],"annotations_sha256":digests[1],
        "explicit_reference_image_sha256":None if research_mode else digests[2],
        "in_memory_development_reference_pixel_sha256":digests[2] if research_mode else None,
        "in_memory_development_reference_source_frame":in_memory_frame_number if research_mode else None,
        "reference_selection_status":(
            "UNAPPROVED_LABEL_NORMAL_SELF_SOURCE_NOT_INDEPENDENTLY_VALIDATED"
            if research_mode else "USER_SUPPLIED_FILE_NOT_INDEPENDENTLY_VERIFIED"
        ),
        "limitations":[
            "Unapproved researcher-supplied same-camera reference is NOT proven camera provenance",
            "Already-inspected datasets are development, not independent held-out",
            "No source/reference matches or correct-cause ground truth independently verified",
            "No reviewed-reference private storage or officer authorization used",
            "Scene hypotheses are not tampering proof or verification of visible activity",
            "Nothing suppresses warnings or changes live camera, reference or attendance",
        ],
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--video",required=True,type=Path)
    p.add_argument("--annotations",required=True,type=Path)
    p.add_argument("--reference-image",required=True,type=Path)
    p.add_argument("--video-sha256",required=True)
    p.add_argument("--annotations-sha256",required=True)
    p.add_argument("--reference-sha256",required=True)
    p.add_argument("--out",required=True,type=Path)
    p.add_argument("--sample-seconds",type=float,default=1.0)
    p.add_argument("--preview-seconds",type=float)
    p.add_argument("--development-only",action="store_true")
    args=p.parse_args()
    if not args.development_only:
        p.error("Explicit --development-only is required; no approved/operational reference")
    if args.out.suffix.lower()!=".json" or args.out.exists():
        p.error("New .json output required; reports are never overwritten")
    report=replay(
        video=args.video,annotations=args.annotations,reference=args.reference_image,
        video_sha256=args.video_sha256,annotations_sha256=args.annotations_sha256,
        reference_sha256=args.reference_sha256,
        sample_seconds=args.sample_seconds,preview_seconds=args.preview_seconds,
    )
    args.out.parent.mkdir(parents=True,exist_ok=True)
    with args.out.open("x",encoding="utf-8") as fd:
        json.dump(report,fd,indent=2,sort_keys=True)
        fd.write("\n")
    print(json.dumps({
        "status":report["status"],
        "normal_review_fraction":report["raw_camera_review_fraction_by_class"]["normal"],
        "normal_review_episodes_per_hour":report["new_normal_review_episodes_per_normal_hour"],
        "moved_fresh_events":report["fresh_event_review_counts"].get("moved",0),
        "moved_events":report["annotated_event_counts"].get("moved",0),
        "report":str(args.out.resolve()),
    },indent=2))


if __name__=="__main__":
    main()
