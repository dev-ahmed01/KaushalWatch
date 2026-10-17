"""Synthetic full-recording replay and fail-closed input tests, no S3 needed."""
from __future__ import annotations

import csv
import hashlib

import cv2
import numpy as np
import pytest

from app.services.camera_reference_offline_benchmark import evaluate_recording, sha256


class StubSession:
    reference_digest="a"*64
    revision=3
    review_id="synthetic-independent-review"
    def __init__(self, alerts=()):
        self.calls=0
        self.alerts=set(alerts)
        self.steps=[]
    def observe(self,frame,seconds):
        assert frame.dtype==np.uint8
        self.steps.append(seconds)
        self.calls+=1
        flag=self.calls in self.alerts
        return {
            "status":"OFFLINE_FIXED_APPROVED_REFERENCE_SHADOW_ONLY",
            "decision":"SPATIAL_SCENE_REVIEW" if flag else "NO_SHADOW_REVIEW",
            "review_cue":flag,
            "evidence_status":"SUFFICIENT_TILES",
        }


def build(tmp_path,classes):
    video=tmp_path/"synthetic.avi"
    labels=tmp_path/"annotations.csv"
    w=cv2.VideoWriter(str(video),cv2.VideoWriter_fourcc(*"MJPG"),3,(64,64))
    assert w.isOpened()
    for idx,kind in enumerate(classes):
        image=np.full((64,64,3),idx%255,dtype=np.uint8)
        w.write(image)
    w.release()
    with labels.open("w",newline="",encoding="utf-8") as file:
        writer=csv.writer(file)
        for index,kind in enumerate(classes,1):
            writer.writerow([index,kind,0,0,0])
    return video,labels


def run(video,labels,session,**kwargs):
    return evaluate_recording(
        video=video,labels=labels,session=session,
        expected_video_sha256=sha256(video),
        expected_labels_sha256=sha256(labels),
        **kwargs,
    )


def test_whole_recording_maintains_state_and_counts_new_event(tmp_path):
    # Eight seconds normal; six seconds annotated movement; eight normal.
    labels=[0]*24+[3]*18+[0]*24
    video,annotations=build(tmp_path,labels)
    session=StubSession(alerts=range(7,28))
    result=run(video,annotations,session,sample_seconds=1.0)
    assert result["status"]=="COMPLETE_OFFLINE_REFERENCE_REPLAY_DEVELOPMENT_NOT_HELD_OUT"
    assert result["production_qualified"] is False
    assert result["production_integration"] is False
    assert session.calls==22
    assert result["sampled_by_class"]=={"normal":16,"moved":6}
    assert result["normal_review_fraction"]==round(10/16,6)
    assert result["per_class"]["moved"]["events"]==1
    assert result["per_class"]["moved"]["events_preexisting_review"]==1
    assert result["per_class"]["moved"]["fresh_review_events"]==0
    assert result["new_normal_review_episodes"]==1
    assert all(abs(s-1)<0.01 for s in session.steps)
    assert "video_sha256" in result and "labels_sha256" in result


def test_new_movement_onset_detected_only_after_signal_rises(tmp_path):
    labels=[0]*18+[3]*15+[0]*9
    video,annotations=build(tmp_path,labels)
    # Scene cue appears after onset and is then continuously sustained.
    session=StubSession(alerts=range(8,13))
    result=run(video,annotations,session)
    moved=result["per_class"]["moved"]
    assert moved["events"]==1
    assert moved["fresh_review_events"]==1
    assert moved["fresh_review_fraction"]==1
    assert moved["events_preexisting_review"]==0
    assert moved["max_fresh_delay_seconds"]==1.0  # three frames at 3 FPS


def test_preview_cannot_be_reported_as_full_recording(tmp_path):
    video,annotations=build(tmp_path,[0]*60)
    session=StubSession()
    result=run(video,annotations,session,preview_seconds=5)
    assert result["status"]=="PREVIEW_ONLY_OFFLINE_REFERENCE_REPLAY_NOT_HELD_OUT"
    assert result["evaluated_frames"]<result["source_frames"]
    assert session.calls==5


def test_hash_mismatch_aborts_without_reading_frames(tmp_path):
    video,annotations=build(tmp_path,[0]*30)
    session=StubSession()
    with pytest.raises(ValueError,match="digest mismatch"):
        evaluate_recording(
            video=video,labels=annotations,session=session,
            expected_video_sha256="0"*64,expected_labels_sha256=sha256(annotations),
        )
    assert session.calls==0


def test_mismatched_frame_index_aborts(tmp_path):
    video,annotations=build(tmp_path,[0]*12)
    rows=annotations.read_text().splitlines()
    rows[3]="99,0,0,0,0"
    annotations.write_text("\n".join(rows)+"\n")
    with pytest.raises(ValueError,match="Label frame/class mismatch"):
        run(video,annotations,StubSession())


def test_extra_annotations_rejected_on_full_replay(tmp_path):
    video,annotations=build(tmp_path,[0]*12)
    with annotations.open("a") as f:
        f.write("13,0,0,0,0\n")
    with pytest.raises(ValueError,match="extra rows"):
        run(video,annotations,StubSession())


def test_no_zero_or_nan_sampling(tmp_path):
    video,annotations=build(tmp_path,[0]*12)
    for invalid in (0,-1,float("nan"),float("inf")):
        with pytest.raises(ValueError,match="finite"):
            run(video,annotations,StubSession(),sample_seconds=invalid)


def test_invalid_signal_does_not_count_as_valid_review(tmp_path):
    video,annotations=build(tmp_path,[0]*12)
    class BadSession(StubSession):
        def observe(self,frame,seconds):
            d=super().observe(frame,seconds)
            d["review_cue"]="true"
            return d
    with pytest.raises(ValueError,match="Boolean"):
        run(video,annotations,BadSession())



def test_notification_sweep_preserves_raw_detector_and_event_scores(tmp_path):
    classes=[0]*60+[3]*30+[0]*60
    video,annotations=build(tmp_path,classes)
    # Scene review originates during normal, persists across onset, then
    # fluctuates. Notification coalescing must NOT change either cue or the
    # original preexisting-at-onset semantics.
    flagged=set(range(5,41))|set(range(45,48))
    result=run(video,annotations,StubSession(alerts=flagged))
    normal_samples=result["sampled_by_class"]["normal"]
    assert result["normal_review_fraction"]==round(
        result["review_samples_by_class"]["normal"]/normal_samples,6
    )
    assert result["per_class"]["moved"]["events"]==1
    assert result["per_class"]["moved"]["events_preexisting_review"]==1
    assert result["per_class"]["moved"]["fresh_review_events"]==0
    sweep=result["operator_notification_shadow_sweep"]
    assert len(sweep)==6
    assert result["notifications_are_not_detector_predictions"]
    for preset,report in sweep.items():
        assert report["raw_review_samples_unchanged"]==sum(
            result["review_samples_by_class"].values()
        )
        assert report["raw_unknown_samples_unchanged"]==sum(
            result["unknown_samples_by_class"].values()
        )
        assert report["status"]=="OFFLINE_NOTIFICATION_CANDIDATE_NOT_DEPLOYED"
        assert not report["automatic_camera_recovery"]
        assert not report["automatic_reference_reset"]
        assert not report["attendance_or_compliance_actions"]
        assert report["notifications_by_annotated_class"]["moved"] is not None


def test_low_texture_global_fallback_keeps_quality_uncertainty(tmp_path):
    video,annotations=build(tmp_path,[0]*120)
    class UnknownWithFallback(StubSession):
        def observe(self,frame,seconds):
            result=super().observe(frame,seconds)
            result["evidence_status"]="UNKNOWN_LOW_TEXTURE"
            result["decision"]="LOW_TEXTURE_GLOBAL_SCENE_REVIEW"
            result["review_cue"]=True
            return result
    result=run(video,annotations,UnknownWithFallback())
    assert result["unknown_samples_by_class"]["normal"]==40
    assert result["normal_review_fraction"]==1.0
    report=result["operator_notification_shadow_sweep"]["clear60_remind900"]
    assert report["raw_unknown_samples_unchanged"]==40
    assert report["raw_review_samples_unchanged"]==40
    assert report["scene_review_active_at_end"]
    assert report["quality_review_active_at_end"]
    assert report["notification_counts"]["QUALITY_UNKNOWN_REVIEW"]==1
    assert report["notification_counts"]["SCENE_REVIEW_OPEN"]==1
