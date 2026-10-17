"""Phase 3J shadow notification regression: cue accounting NEVER suppressed."""
from __future__ import annotations

import pytest

from app.services.camera_reference_notification_shadow import (
    ReviewNotificationShadow, OFFLINE_PRESETS,
)


def tick(tracker, seconds, *, alert=False, evidence="SUFFICIENT_TILES"):
    observed=[]
    for _ in range(seconds):
        observed.extend(tracker.observe(
            review_cue=alert, evidence_status=evidence, sample_seconds=1.0
        ))
    return observed


def test_sustained_review_cue_is_visible_at_every_sample_but_notification_grouped():
    tracker=ReviewNotificationShadow(clear_seconds=60,reminder_seconds=30)
    actions=tick(tracker,100,alert=True)
    assert actions.count("SCENE_REVIEW_OPEN")==1
    assert actions.count("SCENE_REVIEW_REMINDER")==3
    assert tracker.scene_active
    assert tracker.raw_review_samples==100
    assert tracker.samples==100
    report=tracker.summary()
    assert report["raw_review_samples_unchanged"]==100
    assert report["automatic_camera_recovery"] is False
    assert report["automatic_reference_reset"] is False
    assert report["attendance_or_compliance_actions"] is False


def test_brief_cue_gaps_do_not_flood_inbox_or_claim_recovery():
    tracker=ReviewNotificationShadow(clear_seconds=60,reminder_seconds=900)
    notices=(tick(tracker,10,alert=True)
             +tick(tracker,20,alert=False)
             +tick(tracker,10,alert=True))
    assert notices.count("SCENE_REVIEW_OPEN")==1
    assert "SCENE_CUE_CLEARED_REVIEW_PENDING" not in notices
    assert tracker.raw_review_samples==20
    assert tracker.scene_active


def test_low_texture_unknown_never_counts_as_camera_recovery():
    tracker=ReviewNotificationShadow(
        clear_seconds=60,reminder_seconds=100,
        quality_start_seconds=30,quality_clear_seconds=60,
    )
    tick(tracker,15,alert=True)
    notices=tick(tracker,90,evidence="UNKNOWN_LOW_TEXTURE")
    assert tracker.scene_active
    assert tracker.clean_scene_seconds==0
    assert tracker.quality_active
    assert "QUALITY_UNKNOWN_REVIEW" in notices
    assert "SCENE_CUE_CLEARED_REVIEW_PENDING" not in notices
    assert tracker.raw_unknown_samples==90
    # 59 valid samples are not enough to assert even a cue-clear.
    notices=tick(tracker,59)
    assert tracker.scene_active
    assert "SCENE_CUE_CLEARED_REVIEW_PENDING" not in notices
    assert "QUALITY_CUE_CLEARED_UNVERIFIED" not in notices
    final=tick(tracker,1)
    assert final==["SCENE_CUE_CLEARED_REVIEW_PENDING","QUALITY_CUE_CLEARED_UNVERIFIED"]
    assert tracker.scene_active is False
    assert tracker.quality_active is False
    assert tracker.scene_cue_cleared_pending_human==1
    assert tracker.summary()["automatic_camera_recovery"] is False


def test_a_cleared_notification_cycle_can_report_new_review_cue():
    tracker=ReviewNotificationShadow(clear_seconds=30,reminder_seconds=900)
    a=tick(tracker,30,alert=True)
    b=tick(tracker,30)
    c=tick(tracker,1,alert=True)
    assert a.count("SCENE_REVIEW_OPEN")==1
    assert b==["SCENE_CUE_CLEARED_REVIEW_PENDING"]
    assert c==["SCENE_REVIEW_OPEN"]
    assert tracker.raw_review_samples==31


def test_global_fallback_review_during_spatial_unknown_is_still_visible():
    tracker=ReviewNotificationShadow(clear_seconds=60,reminder_seconds=900)
    noticed=tracker.observe(
        review_cue=True, evidence_status="UNKNOWN_LOW_TEXTURE",
        sample_seconds=1,
    )
    assert noticed==("SCENE_REVIEW_OPEN",)
    assert tracker.raw_review_samples==1
    assert tracker.raw_unknown_samples==1
    assert tracker.scene_active


@pytest.mark.parametrize("invalid",[
    {"review_cue":"true","evidence_status":"SUFFICIENT_TILES","sample_seconds":1},
    {"review_cue":True,"evidence_status":"WARMUP","sample_seconds":1},
    {"review_cue":False,"evidence_status":"UNVERIFIED_GOOD","sample_seconds":1},
    {"review_cue":True,"evidence_status":"SUFFICIENT_TILES","sample_seconds":0},
    {"review_cue":True,"evidence_status":"SUFFICIENT_TILES","sample_seconds":float("nan")},
])
def test_invalid_observations_never_advance_tracker(invalid):
    tracker=ReviewNotificationShadow()
    with pytest.raises(ValueError):
        tracker.observe(**invalid)
    assert tracker.elapsed==0
    assert tracker.samples==0
    assert tracker.notifications=={}


@pytest.mark.parametrize("invalid",[-1,0,float("inf"),float("nan"),True])
def test_unsafe_notification_settings_rejected(invalid):
    with pytest.raises(ValueError):
        ReviewNotificationShadow(clear_seconds=invalid)


def test_all_sweep_presets_are_bounded_and_explicit():
    assert len(OFFLINE_PRESETS)==6
    assert OFFLINE_PRESETS["clear60_remind900"]==(60.0,900.0)
    for clear,remind in OFFLINE_PRESETS.values():
        tracker=ReviewNotificationShadow(clear_seconds=clear,reminder_seconds=remind)
        assert tracker.summary()["automatic_reference_reset"] is False
