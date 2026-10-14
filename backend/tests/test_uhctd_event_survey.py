"""Stratified UHCTD short-window survey tests use only synthetic footage."""
import csv
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from survey_uhctd_events import (
    annotation_intervals, select_spans, survey,
)


def test_selection_uses_distinct_extents_and_no_event_before_context(tmp_path):
    rows=[]
    cursor=1
    for kind, extent in [(0,"0"),(1,"0.25"),(0,"0"),(1,"0.5"),
                         (0,"0"),(2,"0.25"),(0,"0"),(2,"0.5"),
                         (0,"0"),(3,"0.25"),(0,"0"),(3,"0.5"),(0,"0")]:
        start=cursor
        cursor+=70
        rows.extend([[i,kind,extent,0,0] for i in range(start,cursor)])
    path=tmp_path/"labels.csv"
    with path.open("w",newline="") as handle:
        writer=csv.writer(handle)
        writer.writerows(rows)
    runs,total=annotation_intervals(path)
    spans=select_spans(runs,10,2,1,2.,1.,3.)
    assert len([s for s in spans if s["kind"] != 0])==6
    assert {s["extent"] for s in spans if s["kind"] == 1}=={"0.25","0.5"}
    assert all(s["start"] < s["onset"] <= s["end"] for s in spans if s["kind"] != 0)


def test_full_synthetic_survey_writes_only_small_reports(tmp_path):
    video=tmp_path/"synthetic.avi"
    labels=tmp_path/"labels.csv"
    vw=cv2.VideoWriter(str(video),cv2.VideoWriter_fourcc(*"MJPG"),10,(80,60))
    assert vw.isOpened()
    rows=[]
    segments=[(0,150),(1,50),(0,150),(2,50),(0,150),(3,50),(0,150)]
    n=0
    try:
        for cls,length in segments:
            for _ in range(length):
                n+=1
                frame=np.full((60,80,3),120,dtype=np.uint8)
                cv2.rectangle(frame,(15,10),(55,48),(220,220,220),2)
                if cls == 1:
                    frame[:30,:40]=200
                elif cls == 2:
                    frame=cv2.GaussianBlur(frame,(15,15),5)
                elif cls == 3:
                    frame=np.roll(frame,20,axis=1)
                frame[-1,-1]=n%4
                vw.write(frame)
                rows.append([n,cls,.5,0,0])
    finally:
        vw.release()
    with labels.open("w",newline="") as f:
        writer=csv.writer(f)
        writer.writerows(rows)
    out=tmp_path/"results"
    result=survey(video,labels,out,events_per_class=1,normal_windows=2,
                  event_seconds=3,context_seconds=2,normal_seconds=3)
    assert result["evaluation_status"].startswith("STRATIFIED_DEVELOPMENT")
    assert len(list(out.iterdir()))==2
    assert result["by_type"]["covered"]["spans"]==1
    assert result["by_type"]["normal"]["spans"]==2


def test_frame_discontinuity_rejected(tmp_path):
    path=tmp_path/"bad.csv"
    path.write_text("1,0,0,0,0\n3,1,0.25,0,0\n")
    with pytest.raises(ValueError,match="Unexpected frame"):
        annotation_intervals(path)
