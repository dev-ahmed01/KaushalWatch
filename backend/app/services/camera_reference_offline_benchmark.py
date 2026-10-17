"""Numeric-only continuous replay with a checked offline camera-reference session.

Development footage labels: headerless, 1-based frame/class/extent columns.
No footage is exported. Frame/video hashes are mandatory and checked BEFORE
the recording is decoded; no full-recording success if annotations mismatch.
"""
from __future__ import annotations

import csv
import hashlib
import math
from collections import Counter
from pathlib import Path

import cv2

CLASSES={0:"normal",1:"covered",2:"defocused",3:"moved"}


def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024*1024),b""):
            h.update(block)
    return h.hexdigest()


def _ratio(a,b):
    return round(a/b,6) if b else None


def evaluate_recording(*, video: Path, labels: Path, session,
                       expected_video_sha256: str, expected_labels_sha256: str,
                       sample_seconds: float=1.0, preview_seconds: float|None=None) -> dict:
    video,labels=Path(video),Path(labels)
    if not video.is_file() or not labels.is_file():
        raise ValueError("Recording and headerless annotations must exist")
    if (not math.isfinite(sample_seconds) or sample_seconds<=0 or
            (preview_seconds is not None and (
                not math.isfinite(preview_seconds) or preview_seconds<=0))):
        raise ValueError("Positive finite replay cadence required")
    if not all(isinstance(v,str) and len(v)==64 and
               all(ch in "0123456789abcdef" for ch in v)
               for v in (expected_video_sha256,expected_labels_sha256)):
        raise ValueError("Two explicit lowercase source SHA-256 hashes required")
    video_sha=sha256(video)
    label_sha=sha256(labels)
    if video_sha!=expected_video_sha256 or label_sha!=expected_labels_sha256:
        raise ValueError("Replay input digest mismatch: no analysis performed")

    cap=cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise ValueError("Video cannot be decoded")
    try:
        fps=float(cap.get(cv2.CAP_PROP_FPS))
        frame_count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if not math.isfinite(fps) or fps<=0 or frame_count<=0:
            raise ValueError("Video lacks valid FPS/frame count")
        step=max(1,round(sample_seconds*fps))
        interval=step/fps
        limit=frame_count if preview_seconds is None else min(
            frame_count,math.ceil(preview_seconds*fps)
        )
        full=limit==frame_count
        sampled=Counter()
        flagged=Counter()
        unknown=Counter()
        episode_count=Counter()
        event_counts=Counter()
        events=[]
        active=None
        prev_kind=None
        prev_alert=False
        normal_hours=0.0
        with labels.open("r",newline="",encoding="utf-8-sig") as stream:
            rows=csv.reader(stream,strict=True)
            for index in range(limit):
                row=next(rows,None)
                if row is None or len(row)<5:
                    raise ValueError(f"Missing annotation at frame {index+1}")
                try:
                    rownum=int(row[0].strip())
                    cls=int(row[1].strip())
                except (TypeError,ValueError) as exc:
                    raise ValueError(f"Invalid annotation frame {index+1}") from exc
                if rownum!=index+1 or cls not in CLASSES:
                    raise ValueError(f"Label frame/class mismatch at {index+1}")
                if cls!=prev_kind:
                    if active is not None:
                        active["end_frame"]=index
                        events.append(active)
                        active=None
                    if cls>0:
                        active={
                            "class":CLASSES[cls],
                            "start_frame":index+1,
                            "end_frame":None,
                            "preexisting_at_onset":prev_alert,
                            "fresh_review_frame":None,
                            "any_review_samples":0,
                        }
                    prev_kind=cls
                if cls==0:
                    normal_hours+=1/fps/3600
                if not cap.grab():
                    raise ValueError(f"Video decode ended at frame {index+1}")
                if index%step:
                    continue
                success,frame=cap.retrieve()
                if not success or frame is None:
                    raise ValueError(f"Frame decode failure {index+1}")
                signal=session.observe(frame,interval)
                if signal.get("status")!="OFFLINE_FIXED_APPROVED_REFERENCE_SHADOW_ONLY":
                    raise ValueError("Unrecognized session advisory response")
                review=signal.get("review_cue")
                if type(review) is not bool:
                    raise ValueError("Offline session must supply Boolean review cue")
                name=CLASSES[cls]
                sampled[name]+=1
                if signal["decision"]=="UNKNOWN_LOW_TEXTURE":
                    unknown[name]+=1
                if review:
                    flagged[name]+=1
                    if not prev_alert and cls==0:
                        episode_count["normal"]+=1
                    if cls>0 and active is not None:
                        active["any_review_samples"]+=1
                        if not prev_alert and not active["preexisting_at_onset"] and active["fresh_review_frame"] is None:
                            active["fresh_review_frame"]=index+1
                prev_alert=review

            if active:
                active["end_frame"]=limit
                events.append(active)
            if full and next(rows,None) is not None:
                raise ValueError("Annotations contain extra rows beyond complete video")
    finally:
        cap.release()

    per_class={}
    for cls in ("covered","defocused","moved"):
        matched=[x for x in events if x["class"]==cls]
        fresh=[x for x in matched if x["fresh_review_frame"] is not None]
        delays=[(x["fresh_review_frame"]-x["start_frame"])/fps for x in fresh]
        per_class[cls]={
            "events":len(matched),"fresh_review_events":len(fresh),
            "fresh_review_fraction":_ratio(len(fresh),len(matched)),
            "events_preexisting_review":sum(x["preexisting_at_onset"] for x in matched),
            "events_with_review_samples":sum(x["any_review_samples"]>0 for x in matched),
            "max_fresh_delay_seconds":round(max(delays),3) if delays else None,
        }

    return {
        "status":("COMPLETE_OFFLINE_REFERENCE_REPLAY_DEVELOPMENT_NOT_HELD_OUT"
                  if full else "PREVIEW_ONLY_OFFLINE_REFERENCE_REPLAY_NOT_HELD_OUT"),
        "production_qualified":False,"production_integration":False,
        "video_sha256":video_sha,"labels_sha256":label_sha,
        "reference_sha256":session.reference_digest,
        "reference_revision":session.revision,
        "reference_review_id":session.review_id,
        "reference_basis":"postgreSQL_reviewed_private_artifact_offline_only",
        "video_fps":fps,"source_frames":frame_count,
        "evaluated_frames":limit,"sample_step_frames":step,
        "effective_sample_seconds":interval,
        "normal_annotated_hours":round(normal_hours,6),
        "sampled_by_class":dict(sampled),
        "review_samples_by_class":dict(flagged),
        "unknown_samples_by_class":dict(unknown),
        "normal_review_fraction":_ratio(flagged["normal"],sampled["normal"]),
        "new_normal_review_episodes":episode_count["normal"],
        "new_normal_review_episodes_per_normal_hour":(
            round(episode_count["normal"]/normal_hours,6) if normal_hours else None
        ),
        "per_class":per_class,
        "limitations":[
            "The offline source video has a supplied digest, not proven device origin",
            "Human reviewer attestations and S3 matching do not prove physical camera authenticity",
            "Annotation-normal excludes labeled tamper but not all poor or changed visibility",
            "Day 3/Day 4 remain contaminated development recordings, not untouched hold-out",
            "Continuous session state retained; no auto-recovery or automatic baseline replacement",
            "Review cues are not proof of motion or intent",
            "No output can change attendance, evidence validity or compliance",
            "Release qualification remains blocked pending independent blind site testing",
        ],
    }
