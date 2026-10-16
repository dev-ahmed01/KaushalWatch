"""Only synthetic inputs; no restricted CCTV, frames or external footage."""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np
import pytest

from app.services.camera_shadow_fusion import (
    ShadowFusionProbe,
    combine_shadow_evidence,
)

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from score_uhctd_shadow_fusion import fresh_event, score_csv  # noqa: E402


def fused(status, spatial=False, global_alert=False, global_quality_limited=False):
    return combine_shadow_evidence(
        {"evidence_status": status, "review_55": spatial},
        {
            "persistent_review": global_alert,
            "quality_limited": global_quality_limited,
        },
    )


def test_spatial_alert_is_advisory_and_has_priority():
    report = fused("SUFFICIENT_TILES", spatial=True, global_alert=False)
    assert report["decision"] == "SPATIAL_SCENE_REVIEW"
    assert report["review_cue"]
    assert not report["production_integration"]
    assert "tamper_suspected" not in report


def test_sufficient_spatial_negative_does_not_accept_global_false_alarm():
    report = fused("SUFFICIENT_TILES", global_alert=True)
    assert report["decision"] == "NO_SHADOW_REVIEW"
    assert not report["review_cue"]


def test_low_texture_can_use_persistent_global_as_review_only():
    report = fused("UNKNOWN_LOW_TEXTURE", global_alert=True)
    assert report["decision"] == "LOW_TEXTURE_GLOBAL_SCENE_REVIEW"
    assert report["review_cue"]
    assert report["interpretation"] == "OFFICER_REVIEW_ONLY_NOT_TAMPER_OR_MOVEMENT_PROOF"


def test_low_texture_global_signal_with_unreliable_texture_is_unknown():
    report = fused(
        "UNKNOWN_LOW_TEXTURE", global_alert=True, global_quality_limited=True
    )
    assert report["decision"] == "UNKNOWN_LOW_TEXTURE"
    assert not report["review_cue"]


def test_low_texture_without_global_evidence_remains_unknown():
    report = fused("UNKNOWN_LOW_TEXTURE")
    assert report["decision"] == "UNKNOWN_LOW_TEXTURE"
    assert not report["review_cue"]


def test_warmup_does_not_raise_review_even_if_global_reports_change():
    report = fused("WARMUP", global_alert=True)
    assert report["decision"] == "WARMUP"
    assert not report["review_cue"]


@pytest.mark.parametrize("status,spatial,global_alert", [
    ("INVALID", False, False),
    ("UNKNOWN_LOW_TEXTURE", True, False),
    ("WARMUP", True, False),
    ("SUFFICIENT_TILES", None, False),
    ("SUFFICIENT_TILES", False, None),
])
def test_malformed_or_conflicting_probe_evidence_rejected(
    status, spatial, global_alert
):
    with pytest.raises(ValueError):
        fused(status, spatial=spatial, global_alert=global_alert)


def test_probe_exercises_both_shadow_engines_without_modifying_camera_trust():
    probe = ShadowFusionProbe()
    blank = np.full((80, 80, 3), 65, dtype=np.uint8)
    first = probe.observe(blank, 1 / 3)
    assert first["decision"] == "WARMUP"
    for _ in range(90):
        last = probe.observe(blank, 1 / 3)
    assert last["decision"] == "UNKNOWN_LOW_TEXTURE"
    assert not last["review_cue"]


def test_fresh_event_requires_new_onset_not_preexisting_warning():
    rows = [
        {"post_onset": False, "fusion": True},
        {"post_onset": True, "fusion": True},
        {"post_onset": True, "fusion": False},
        {"post_onset": True, "fusion": True},
    ]
    assert fresh_event(rows, "fusion") == (False, True)


def test_csv_replay_preserves_unknown_and_avoids_normal_false_alarm(tmp_path):
    path = tmp_path / "samples.csv"
    fieldnames = [
        "span", "kind", "frame", "post_onset",
        "evidence_status", "review_55", "global_review",
        "global_quality_limited",
    ]
    rows = [
        # Low texture: global fallback creates a fresh advisory review.
        ("moved_1_at_5", 3, 1, False, "WARMUP", False, False, False),
        ("moved_1_at_5", 3, 2, False, "UNKNOWN_LOW_TEXTURE", False, False, False),
        ("moved_1_at_5", 3, 5, True, "UNKNOWN_LOW_TEXTURE", False, True, False),
        # A global-only nuisance change in a sufficient-texture scene is ignored.
        ("normal_control_1", 0, 10, False, "SUFFICIENT_TILES", False, True, False),
        ("normal_control_1", 0, 11, False, "SUFFICIENT_TILES", False, True, False),
        # Textured spatial event is still detected when global is negative.
        ("moved_2_at_25", 3, 20, False, "SUFFICIENT_TILES", False, False, False),
        ("moved_2_at_25", 3, 25, True, "SUFFICIENT_TILES", True, False, False),
        # Uninformative reference remains unknown, not an all-clear.
        ("normal_control_2", 0, 40, False, "UNKNOWN_LOW_TEXTURE", False, True, True),
    ]
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output)
        writer.writerow(fieldnames)
        writer.writerows(rows)
    result = score_csv(path)
    comparisons = result["comparisons"]
    assert comparisons["fusion"]["fresh_moved_review_events"] == 2
    assert comparisons["fusion"]["normal_controls_with_review"] == 0
    assert comparisons["global"]["normal_controls_with_review"] == 2
    assert comparisons["spatial"]["fresh_moved_review_events"] == 1
    assert result["qualification"] == "NOT_HELD_OUT_NOT_PRODUCTION_APPROVED"
    assert result["unknown_low_texture_samples"] == 3


def test_csv_replay_rejects_invalid_boolean_and_missing_columns(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("span,kind,frame,post_onset\nnormal_control_1,0,1,False\n")
    with pytest.raises(ValueError, match="Missing required"):
        score_csv(path)
