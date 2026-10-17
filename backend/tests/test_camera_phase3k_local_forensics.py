"""No-cloud Phase3K local research replay tests with generated-only images."""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"scripts"))
from run_phase3k_local_forensics import replay  # noqa: E402
from app.services.camera_reference_offline_benchmark import sha256


def fixture(tmp_path):
    rng=np.random.default_rng(12345)
    image=rng.integers(30,220,(144,192,3),dtype=np.uint8)
    ref=tmp_path/"source.png"
    assert cv2.imwrite(str(ref),image)
    video=tmp_path/"synthetic.avi"
    labels=tmp_path/"annotations.csv"
    writer=cv2.VideoWriter(str(video),cv2.VideoWriter_fourcc(*"MJPG"),3,(192,144))
    assert writer.isOpened()
    events=[0]*12+[3]*12+[0]*12
    for i in range(len(events)):
        frame=image.copy()
        if 12<=i<24:
            frame=cv2.warpAffine(
                frame,np.float32([[1,0,6],[0,1,4]]),(192,144),
                borderMode=cv2.BORDER_REFLECT,
            )
        writer.write(frame)
    writer.release()
    with labels.open("w",newline="") as f:
        out=csv.writer(f)
        for n,kind in enumerate(events,1):
            out.writerow((n,kind,0,0,0))
    return ref,video,labels


def run(paths, **kw):
    ref,video,labels=paths
    return replay(
        reference=ref,video=video,annotations=labels,
        reference_sha256=sha256(ref),video_sha256=sha256(video),
        annotations_sha256=sha256(labels),**kw,
    )


def test_local_research_replay_is_numeric_unqualified_and_fixed(tmp_path):
    files=fixture(tmp_path)
    result=run(files)
    assert result["status"]=="FULL_DEVELOPMENT_CAUSE_REPLAY_UNAPPROVED_REFERENCE_NOT_HELD_OUT"
    assert result["evaluated_frames"]==36
    assert result["annotated_event_counts"]["moved"]==1
    assert result["source_is_held_out"] is False
    assert result["reference_origin_independently_verified"] is False
    assert result["automatic_reference_reset"] is False
    assert not result["production_integration"]
    assert result["cause_inspections_by_class"]["normal"]>0
    assert result["cause_inspections_by_class"]["moved"]>0
    assert result["explicit_reference_image_sha256"]==sha256(files[0])
    comparison=result["counterfactual_scene_gate_comparison"]
    assert comparison["status"]=="FULL_RECORDING_COUNTERFACTUAL_DEVELOPMENT_NOT_HELD_OUT"
    assert comparison["deployable_candidate_selected"] is None
    assert set(comparison["candidate_comparisons"])=={
        "frozen_baseline","photometric_defer","localized_defer",
        "photometric_or_local_defer","coherent_translation_only","sustained_raw_20s",
    }
    base=comparison["candidate_comparisons"]["frozen_baseline"]
    assert base["review_samples_by_class"]==result["raw_review_samples_by_class"]
    assert base["events"]["moved"]["fresh_review_events"]==result[
        "fresh_event_review_counts"
    ].get("moved",0)


def test_local_replay_preview_does_not_claim_full_source(tmp_path):
    files=fixture(tmp_path)
    result=run(files,preview_seconds=5)
    assert result["status"]=="PREVIEW_DEVELOPMENT_CAUSE_REPLAY_NOT_HELD_OUT"
    assert result["evaluated_frames"]==15
    assert result["total_frames"]==36


def test_bad_reference_digest_fails_before_processing(tmp_path):
    ref,video,labels=fixture(tmp_path)
    with pytest.raises(ValueError,match="digest mismatch"):
        replay(
            reference=ref,video=video,annotations=labels,
            reference_sha256="0"*64,video_sha256=sha256(video),
            annotations_sha256=sha256(labels),
        )


def test_invalid_labels_fail_closed(tmp_path):
    ref,video,labels=fixture(tmp_path)
    rows=labels.read_text().splitlines()
    rows[2]="123,0,0,0,0"
    labels.write_text("\n".join(rows)+"\n")
    with pytest.raises(ValueError,match="Frame index/class mismatch"):
        run((ref,video,labels))


@pytest.mark.parametrize("cadence",[0,-1,float("nan"),float("inf")])
def test_nonpositive_or_nonfinite_sampling_is_rejected(tmp_path,cadence):
    files=fixture(tmp_path)
    with pytest.raises(ValueError,match="Positive finite"):
        run(files,sample_seconds=cadence)
