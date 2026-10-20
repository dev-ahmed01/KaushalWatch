"""Local-only previously inspected video trace; generated pixels cannot qualify field models."""
from __future__ import annotations

import csv
import json
import stat
from pathlib import Path
import sys

import cv2
import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from scripts.prepare_research_replay import prepare
from scripts.prepare_research_triage_trace import create_trace,write_once


def private_fixture(tmp_path):
    home=tmp_path/"private-source-cache"
    home.mkdir(parents=True)
    data=[
        ("covered_gentle_frame721_onset",1,"covered","gentle",721,1620,684,825),
        ("defocused_strong_frame166275_onset",2,"defocused","strong",166275,167183,166238,166379),
        ("moved_gentle_frame7919_onset",3,"moved","gentle",7919,8818,7882,8023),
        ("normal_control_1",0,"normal","normal",1,720,135,240),
    ]
    rng=np.random.default_rng(73)
    base=rng.integers(0,256,(96,128,3),dtype=np.uint8)
    for idx,(name,kind,label,selection,start,end,clip_start,clip_end) in enumerate(data):
        target=home/(name+".mp4")
        video=cv2.VideoWriter(str(target),cv2.VideoWriter_fourcc(*"mp4v"),3,(128,96))
        if not video.isOpened():
            pytest.skip("OpenCV mp4 writer unavailable")
        for frame_idx in range(clip_end-clip_start+1):
            pixels=base.copy()
            cv2.rectangle(pixels,((frame_idx+idx)%65,10),(95,40),(90+idx*20,20,200),-1)
            video.write(pixels)
        video.release()
    selection=home/"selected_clips.csv"
    with selection.open("w",encoding="utf-8",newline="") as target:
        writer=csv.DictWriter(target,fieldnames=[
            "name","class","label","selection","event_start_frame",
            "event_end_frame","clip_start_frame0","clip_end_frame0"])
        writer.writeheader()
        for name,kind,label,group,start,end,clip_start,clip_end in data:
            writer.writerow({
                "name":name,"class":kind,"label":label,"selection":group,
                "event_start_frame":start,"event_end_frame":end,
                "clip_start_frame0":clip_start,"clip_end_frame0":clip_end,
            })
    catalog=prepare(selection,home)
    (home/"kw-research-replay.local.json").write_text(json.dumps(catalog))
    return home,selection


def test_real_private_source_locked_research_trace_never_qualifies_model(tmp_path):
    home,selection=private_fixture(tmp_path)
    result=create_trace(selection,home)
    assert result["schema"]=="KW_PRIVATE_RESEARCH_TRIAGE_TRACE_V1"
    assert result["independent_holdout"] is False
    assert result["training_centre_validation"] is False
    assert result["model_accuracy_qualified"] is False
    assert result["reference_source"]=="UNVERIFIED_FIRST_VIDEO_FRAME"
    assert result["automatic_enforcement_authorized"] is False
    assert result["sampling"]=="ONE_FPS_SPARSE_LOCAL_DECODE"
    assert len(result["clips"])==4
    assert result["clips"][0]["samples"][0]["frame0"]==0
    assert result["clips"][0]["samples"][0]["second"]==0
    assert any(s["annotation_in_event"] for s in result["clips"][0]["samples"])
    assert all(c["source_sha256"] for c in result["clips"])
    output=home/"kw-research-analysis.local.json"
    write_once(output,result)
    assert stat.S_IMODE(output.stat().st_mode)==0o600
    with pytest.raises(FileExistsError):
        write_once(output,result)


def test_source_or_annotation_drift_refused_before_frame_scoring(tmp_path):
    home,selection=private_fixture(tmp_path)
    file=home/"covered_gentle_frame721_onset.mp4"
    with file.open("ab") as stream:stream.write(b"unexpected")
    with pytest.raises(ValueError,match="changed"):
        create_trace(selection,home)

    home,selection=private_fixture(tmp_path/"another")
    selection.write_text(selection.read_text().replace("covered,gentle", "covered,strong"))
    with pytest.raises(ValueError,match="changed"):
        create_trace(selection,home)


def test_protected_mode_and_checkout_destination_are_denied(tmp_path):
    home,selection=private_fixture(tmp_path)
    with pytest.raises(ValueError,match="Protected mode"):
        create_trace(selection,home,environment="pilot")
    with pytest.raises(ValueError,match="Never write"):
        write_once(ROOT/"forbidden-report.json",{})
