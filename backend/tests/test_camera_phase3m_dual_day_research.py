"""Synthetic private two-day batch harness tests. No CCTV, cloud, or IdP."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"scripts"))
from run_phase3m_dual_day_research import (  # noqa: E402
    run_pair,_choose_reference_index,_memory_sha,_frame_in_memory,_read_source,
    REFERENCE_MIN_NORMAL_SECONDS,
)


def make_day(tmp_path,name,fps,seed):
    folder=tmp_path/name
    folder.mkdir()
    video=folder/"video.avi"
    annotations=folder/"annotations.csv"
    rng=np.random.default_rng(seed)
    base=rng.integers(45,200,(96,128,3),dtype=np.uint8)
    frames=int(fps*104)
    import csv
    writer=cv2.VideoWriter(str(video),cv2.VideoWriter_fourcc(*"MJPG"),fps,(128,96))
    assert writer.isOpened()
    with annotations.open("w",newline="") as out:
        labels=csv.writer(out)
        for i in range(frames):
            kind=3 if fps*94<=i<fps*100 else 0
            img=base.copy()
            if kind==3:
                img=cv2.warpAffine(
                    img,np.float32([[1,0,8],[0,1,5]]),(128,96),
                    borderMode=cv2.BORDER_REFLECT
                )
            writer.write(img)
            labels.writerow([i+1,kind,0,0,0])
    writer.release()
    return video,annotations


@pytest.fixture
def files(tmp_path):
    return (
        make_day(tmp_path,"day3",3,1120),
        make_day(tmp_path,"day4",5,1142),
    )


def invoke(files,out,**kwargs):
    d3,d4=files
    return run_pair(
        day3_video=d3[0],day3_annotations=d3[1],
        day4_video=d4[0],day4_annotations=d4[1],
        run_dir=out,preview_seconds=15,
        sample_seconds=kwargs.pop("sample_seconds",1),**kwargs
    )


def test_selects_first_sufficient_normal_segment_without_exporting_image(files):
    day3=files[0]
    metadata=_read_source(*day3)
    selected,attested=_choose_reference_index(
        day3[1],fps=metadata["fps"],frames=metadata["frames"]
    )
    assert selected==1+(REFERENCE_MIN_NORMAL_SECONDS*3)//2
    assert attested["reference_verified_healthy"] is False
    assert attested["reference_source_authenticated"] is False
    frame=_frame_in_memory(day3[0],frame_number=selected,expected=metadata)
    assert frame.shape==(96,128,3)
    assert len(_memory_sha(frame))==64


def test_preview_requires_separate_full_run_and_never_claims_holdout(files,tmp_path):
    run=tmp_path/"preview-results"
    status=invoke(files,run)
    assert status["status"]=="PHASE3M_PREVIEWS_ONLY_NO_FULL_RECORDING_EVALUATION"
    assert status["production_qualified"] is False
    assert not (run/"full").exists()
    assert not (run/"phase3m_dual_day_comparison.json").exists()
    manifest=json.loads((run/"research_reference_manifest.json").read_text())
    assert manifest["reference_media_exported"] is False
    assert manifest["source_paths_embedded"] is False
    assert manifest["source_provenance_independently_confirmed"] is False
    for day in ("day3","day4"):
        assert manifest["days"][day]["reference_independently_reviewed"] is False
        preview=json.loads((run/"preview"/f"{day}.json").read_text())
        assert preview["status"]=="PREVIEW_DEVELOPMENT_CAUSE_REPLAY_NOT_HELD_OUT"
        assert preview["explicit_reference_image_sha256"] is None
        assert preview["reference_selection_status"].startswith("UNAPPROVED_")
        assert preview["counterfactual_scene_gate_comparison"]["status"]=="PREVIEW_ONLY_COUNTERFACTUAL_NOT_COMPARABLE"
    assert not any(p.suffix.lower() in (".png",".jpeg",".jpg",".avi") for p in run.rglob("*"))


def test_full_pair_runs_all_candidate_rules_and_does_not_choose_any(files,tmp_path):
    run=tmp_path/"full-results"
    final=invoke(files,run,run_full=True)
    assert final["status"]=="PHASE3M_FULL_DUAL_DAY_DEVELOPMENT_REPLAY_COMPLETE_NOT_HELD_OUT"
    assert final["production_qualified"] is False
    compare=json.loads((run/"phase3m_dual_day_comparison.json").read_text())
    assert compare["recommended_for_production"] is None
    assert compare["no_automatic_policy_selection"] is True
    assert len(compare["candidate_results"])==6
    assert compare["candidate_results"]["frozen_baseline"]["status"]=="FROZEN_REFERENCE"
    for name,data in compare["candidate_results"].items():
        assert data["authorized_for_deployment"] is False
    for day in ("day3","day4"):
        report=json.loads((run/"full"/f"{day}.json").read_text())
        assert report["status"]=="FULL_DEVELOPMENT_CAUSE_REPLAY_UNAPPROVED_REFERENCE_NOT_HELD_OUT"
        assert report["source_is_held_out"] is False
        assert report["production_qualified"] is False
        assert report["reference_origin_independently_verified"] is False
        assert report["annotated_event_counts"]["moved"]==1
        assert report["counterfactual_scene_gate_comparison"]["deployable_candidate_selected"] is None
    assert not any(p.suffix.lower() in (".png",".jpeg",".jpg",".avi") for p in run.rglob("*"))


def test_non_normal_initial_section_no_90_second_normal_interval_is_blocked(files,tmp_path):
    video,labels=files[0]
    # Convert periodic normal frames to covered, destroying any 90s stretch.
    lines=labels.read_text().splitlines()
    for pos in range(0,len(lines),30):
        fields=lines[pos].split(",")
        fields[1]="1"
        lines[pos]=",".join(fields)
    labels.write_text("\n".join(lines)+"\n")
    run=tmp_path/"blocked"
    with pytest.raises(ValueError,match="No 90-second"):
        invoke(files,run)
    assert not run.exists()


def test_missing_day_is_rejected_before_writing_any_evidence(files,tmp_path):
    files=((files[0][0],files[0][1]),(tmp_path/"missing.avi",files[1][1]))
    run=tmp_path/"nothing"
    with pytest.raises(ValueError,match="must exist"):
        invoke(files,run)
    assert not run.exists()


def test_identical_sources_not_mislabeled_two_cameras(files,tmp_path):
    originals=(files[0],files[0])
    with pytest.raises(ValueError,match="identical video"):
        invoke(originals,tmp_path/"identical")
    assert not (tmp_path/"identical").exists()


def test_does_not_replace_prior_reports(files,tmp_path):
    run=tmp_path/"safe"
    invoke(files,run)
    with pytest.raises(FileExistsError,match="exists"):
        invoke(files,run)


def test_nonfinite_sampling_rejected(files,tmp_path):
    with pytest.raises(ValueError,match="Positive sample"):
        invoke(files,tmp_path/"invalid",sample_seconds=float("nan"))
