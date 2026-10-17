"""Annotation transitions and cue/recovery boundaries are research-only."""
import pytest

from app.services.camera_incident_continuity_shadow import IncidentContinuityShadow


def observe(model, cls, review, evidence="SUFFICIENT_TILES", seconds=1):
    return model.observe(
        annotation_class=cls,raw_review=review,
        spatial_evidence_status=evidence,sample_seconds=seconds,
    )


def test_day3_style_preexisting_warning_is_not_fresh_incident_detection():
    state=IncidentContinuityShadow(clear_seconds=10)
    for _ in range(20):
        observe(state,0,True)
    start=observe(state,3,True)
    assert start["warning_preexisting_at_new_annotation"] is True
    for _ in range(15):
        observe(state,3,True)
    observe(state,0,True)
    summary=state.summary()
    assert summary["counters"]["annotated_event_onsets"]==1
    assert summary["counters"]["events_warning_preexisting_at_onset"]==1
    assert summary["counters"]["warning_carried_into_annotated_normal"]==1
    assert summary["counters"]["new_raw_review_episodes"]==1
    assert summary["counters"]["normal_review_samples_after_event"]==1
    assert not summary["auto_recovery"]
    assert not summary["auto_reference_reset"]


def test_unknown_quality_never_counts_as_cue_clear():
    tracker=IncidentContinuityShadow(clear_seconds=5)
    observe(tracker,0,True)
    for _ in range(60):
        observe(tracker,0,False,evidence="UNKNOWN_LOW_TEXTURE")
    assert tracker.episode_open is True
    assert tracker.clean_seconds==0
    assert tracker.summary()["counters"]["unknown_cannot_clear_episode_samples"]==60
    for _ in range(4):
        observe(tracker,0,False)
    assert tracker.episode_open
    observe(tracker,0,False)
    assert not tracker.episode_open
    assert tracker.summary()["counters"]["raw_cue_clear_candidates_pending_review"]==1
    assert tracker.summary()["auto_recovery"] is False


def test_new_incident_after_cue_clear_is_new_onset_without_carryover():
    tracker=IncidentContinuityShadow(clear_seconds=3)
    observe(tracker,0,True)
    for _ in range(3):
        observe(tracker,0,False)
    new=observe(tracker,2,False)
    assert not new["warning_preexisting_at_new_annotation"]
    assert tracker.summary()["counters"]["events_without_warning_at_onset"]==1
    assert tracker.summary()["counters"].get("events_warning_preexisting_at_onset",0)==0


@pytest.mark.parametrize("bad",[
    {"annotation_class":4,"raw_review":False,"spatial_evidence_status":"SUFFICIENT_TILES","sample_seconds":1},
    {"annotation_class":0,"raw_review":1,"spatial_evidence_status":"SUFFICIENT_TILES","sample_seconds":1},
    {"annotation_class":0,"raw_review":False,"spatial_evidence_status":"WARMUP","sample_seconds":1},
    {"annotation_class":0,"raw_review":False,"spatial_evidence_status":"SUFFICIENT_TILES","sample_seconds":0},
])
def test_bad_observation_does_not_mutate_timeline(bad):
    tracker=IncidentContinuityShadow()
    with pytest.raises(ValueError):
        tracker.observe(**bad)
    assert tracker.samples==0


def test_preexisting_flag_is_per_onset_not_cumulative():
    tracker=IncidentContinuityShadow(clear_seconds=1)
    observe(tracker,0,True)
    assert observe(tracker,3,True)["warning_preexisting_at_new_annotation"]
    observe(tracker,0,False)
    observe(tracker,0,False)
    second=observe(tracker,2,False)
    assert second["warning_preexisting_at_new_annotation"] is False
