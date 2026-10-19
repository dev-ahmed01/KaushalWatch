"""Prepare read-only source-locked MEVA research replay from already cached clips.

Does not download, upload, copy or modify any video. Source labels are
research interventions, not physical camera diagnosis or centre compliance.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re

SCHEMA="KW_RESEARCH_REPLAY_V1"
PROVENANCE="MEVA_UHCTD_RESEARCH_ANNOTATIONS_NOT_SKILL_CENTRE"
FPS=3
PLAN=(
 ("quality-covered","covered_gentle_frame721_onset","covered","Coverage change"),
 ("quality-defocused","defocused_strong_frame166275_onset","defocused","Focus change"),
 ("quality-moved","moved_gentle_frame7919_onset","moved","Camera alignment change"),
 ("quality-normal","normal_control_1","normal","Normal control"),
)

def sha_file(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda:stream.read(1024*1024),b""):
            h.update(part)
    return h.hexdigest()

def prepare(selection_csv:Path,clip_dir:Path)->dict:
    if not selection_csv.is_file() or not clip_dir.is_dir():
        raise ValueError("Research annotation sheet or cached clips absent")
    with selection_csv.open("r",encoding="utf-8-sig",newline="") as f:
        data=list(csv.DictReader(f))
    if not 4<=len(data)<=100:
        raise ValueError("Invalid research selection count")
    by_name={}
    for entry in data:
        name=entry.get("name","")
        if not re.fullmatch(r"[a-z0-9_]{1,100}",name) or name in by_name:
            raise ValueError("Unsafe or duplicate research source name")
        by_name[name]=entry
    clips=[]
    for alias,name,category,title in PLAN:
        row=by_name.get(name)
        if row is None or row.get("label")!=category:
            raise ValueError("Required event annotation not found")
        filename=name+".mp4"
        source=clip_dir/filename
        if source.is_symlink() or not source.is_file():
            raise ValueError("Research cache missing or symbolic link")
        size=source.stat().st_size
        if not 10000<=size<=16_000_000:
            raise ValueError("Unexpected cached research clip size")
        with source.open("rb") as video:
            if video.read(16)[4:8]!=b"ftyp":
                raise ValueError("Cached file is not an MP4 container")
        try:
            first=int(row["clip_start_frame0"])
            last=int(row["clip_end_frame0"])
            event_first=int(row["event_start_frame"])
            event_last=int(row["event_end_frame"])
        except (KeyError,ValueError,TypeError):
            raise ValueError("Invalid research source frame index") from None
        if not 0<=first<=last or not 0<=event_first<=event_last:
            raise ValueError("Invalid frame interval")
        duration=round((last-first+1)/FPS,3)
        if not 1<=duration<=300:
            raise ValueError("Invalid clip duration")
        start=end=None
        if category!="normal":
            if event_first>last or event_last<first:
                raise ValueError("Event is outside selected source")
            start=round(max(0,(event_first-first)/FPS),3)
            end=round(min(duration,(event_last-first+1)/FPS),3)
            if start>=end:
                raise ValueError("Invalid event window")
        clips.append({"id":alias,"name":title,"filename":filename,
                      "source_sha256":sha_file(source),"bytes":size,
                      "fps":FPS,"duration_seconds":duration,
                      "annotation_class":category,
                      "event_start_seconds":start,"event_end_seconds":end})
    return {"schema":SCHEMA,"provenance":PROVENANCE,
            "annotation_origin":"existing_Meva_UHCTD_Day3_selected_clips_csv",
            "model_inference_qualified":False,
            "training_centre_provenance":False,
            "independent_field_validation":False,"clips":clips}

def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--selection-csv",type=Path,required=True)
    p.add_argument("--clip-dir",type=Path,required=True)
    p.add_argument("--write",action="store_true",
                   help="Write private metadata to the cache; never copy footage")
    args=p.parse_args()
    try:
        receipt=prepare(args.selection_csv,args.clip_dir)
        if args.write:
            output=args.clip_dir/"kw-research-replay.local.json"
            if output.is_symlink():
                raise ValueError("Unsafe local metadata path")
            output.write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n",
                              encoding="utf-8")
        print(json.dumps({"schema":SCHEMA,
              "status":"prepared" if args.write else "verified_without_writing",
              "clips_verified":len(receipt["clips"]),
              "videos_copied":0,"source_bytes_transferred":0,
              "field_camera_accuracy_qualified":False},sort_keys=True))
        return 0
    except (OSError,ValueError,csv.Error):
        print(json.dumps({"schema":SCHEMA,"status":"blocked",
                          "clips_verified":0,"source_bytes_transferred":0,
                          "field_camera_accuracy_qualified":False},sort_keys=True))
        return 2

if __name__=="__main__":
    raise SystemExit(main())
