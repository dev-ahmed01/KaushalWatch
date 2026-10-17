"""Real tiny synthetic AVI->Phase3M report->Phase3N targeted quality path."""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"scripts"))
from run_phase3m_dual_day_research import run_pair  # noqa: E402
from run_phase3n_targeted_visibility import analyze_day, _labels_and_events  # noqa: E402


def make_day(tmp_path,name,fps,seed):
    directory=tmp_path/name
    directory.mkdir()
    path=directory/"video.avi"
    labels=directory/"annotations.csv"
    rng=np.random.default_rng(seed)
    base=rng.integers(35,175,(96,128,3),dtype=np.uint8)
    out=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*"MJPG"),fps,(128,96))
    assert out.isOpened()
    with labels.open("w",newline="") as stream:
        rows=csv.writer(stream)
        for n in range(fps*111):
            kind=(2 if fps*94<=n<fps*99 else
                  3 if fps*103<=n<fps*109 else 0)
            frame=base.copy()
            if kind==2:
                frame=cv2.GaussianBlur(frame,(15,15),4)
            elif kind==3:
                frame=cv2.warpAffine(
                    frame,np.float32([[1,0,6],[0,1,4]]),(128,96),
                    borderMode=cv2.BORDER_REFLECT,
                )
            out.write(frame)
            rows.writerow([n+1,kind,0,0,0])
    out.release()
    return path,labels


@pytest.fixture
def synthetic(tmp_path):
    d3=make_day(tmp_path,"d3",3,14)
    d4=make_day(tmp_path,"d4",5,19)
    output=tmp_path/"prior-completed"
    run_pair(
        day3_video=d3[0],day3_annotations=d3[1],
        day4_video=d4[0],day4_annotations=d4[1],
        run_dir=output,sample_seconds=1,preview_seconds=12,run_full=True,
    )
    return d3,d4,output


def test_targeted_quality_uses_prior_complete_reports_not_detector_replay(synthetic):
    d3,d4,previous=synthetic
    for name,pair in (("day3",d3),("day4",d4)):
        report=analyze_day(
            video=pair[0],annotations=pair[1],
            report_path=previous/"full"/(name+".json"),
        )
        assert report["status"]=="PHASE3N_TARGETED_UNAPPROVED_REFERENCE_DEVELOPMENT_ONLY"
        assert report["production_qualified"] is False
        assert report["complete_video_replayed"] is False
        assert report["frames_images_or_crops_exported"] is False
        assert report["event_counts_checked_against_phase3m"]["defocused"]==1
        assert report["event_counts_checked_against_phase3m"]["moved"]==1
        assert report["sampled_target_frames"]==12
        assert len(report["sampled_positions"])==12
        assert any(x["quality_hypothesis"]=="SHARPNESS_LOSS_COMPATIBLE"
                   and x["target_event_class"]=="defocused"
                   for x in report["sampled_positions"])
        assert all(x["target_event_class"] in ("defocused","moved")
                   for x in report["sampled_positions"])


def test_digest_mismatch_refuses_any_quality_measurement(synthetic):
    d3,_,prior=synthetic
    doc=prior/"full"/"day3.json"
    wrong=doc.parent/"modified-report.json"
    payload=json.loads(doc.read_text())
    payload["video_sha256"]="f"*64
    wrong.write_text(json.dumps(payload))
    with pytest.raises(ValueError,match="pinned local recording"):
        analyze_day(video=d3[0],annotations=d3[1],report_path=wrong)


def test_nonsequential_annotations_fail_before_frame_selection(tmp_path):
    path=tmp_path/"labels.csv"
    path.write_text("1,0,0,0,0\n4,2,0,0,0\n")
    with pytest.raises(ValueError,match="Noncontinuous"):
        _labels_and_events(path,2)


def test_preview_report_is_rejected_by_phase3n(synthetic):
    d3,_,prior=synthetic
    with pytest.raises(ValueError,match="completed"):
        analyze_day(
            video=d3[0],annotations=d3[1],
            report_path=prior/"preview"/"day3.json",
        )
