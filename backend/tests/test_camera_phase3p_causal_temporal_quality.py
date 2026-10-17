"""Phase 3P: causal temporal research observer contracts and adversarial fixtures."""
from __future__ import annotations

from copy import deepcopy
import math

import pytest

from app.services.camera_causal_temporal_quality_shadow import CausalTemporalQualityShadow

PIN = "f" * 64


def quality(
    sharpness=1.0, edges=1.0, contrast=1.0,
    hypothesis="NO_SHARPNESS_LOSS_SIGNAL",
):
    return {
        "status": "OFFLINE_UNCALIBRATED_VISIBILITY_AXES",
        "relative_sharpness": sharpness,
        "relative_edge_fraction": edges,
        "relative_contrast": contrast,
        "quality_hypothesis": hypothesis,
        "production_integration": False,
        "automatic_recovery": False,
        "blur_or_defocus_proven": False,
        "image_usable_verified": False,
        "detector_review_suppressed": False,
    }


def observe(observer, t, sharpness=1.0, *,
            edges=1.0, contrast=1.0,
            hypothesis="NO_SHARPNESS_LOSS_SIGNAL",
            scene=False, spatial="SUFFICIENT_TILES", pin=PIN):
    return observer.observe(
        time_s=t, reference_pixel_sha256=pin,
        features=quality(sharpness, edges, contrast, hypothesis),
        spatial_evidence_status=spatial, raw_scene_review=scene,
    )


def run_seconds(observer, last_second=40, bad_at=30):
    results = []
    for t in range(last_second + 1):
        sharp = 0.1 if t >= bad_at else 1.0
        results.append(observe(observer, float(t), sharp, edges=sharp))
    return results


def test_exact_30_second_causal_reference_no_future_or_same_frame():
    o = CausalTemporalQualityShadow(PIN)
    results = run_seconds(o)
    assert all(r["paired_numeric_ratios"] is None for r in results[:28])
    assert results[29]["comparison_state"] == "PAIRED_UNVERIFIED_NUMERIC_OBSERVATION"
    assert results[29]["past_anchor_age_s"] == 29.0
    assert results[29]["exploratory_sharpness_ratio_at_most_half"] is False
    after = results[30]
    assert after["actual_past_anchor_time_s"] == 0.0
    assert after["past_anchor_age_s"] == 30.0
    assert after["paired_numeric_ratios"]["sharpness"] == 0.1
    assert after["exploratory_sharpness_ratio_at_most_half"] is True
    assert after["incident_closed_or_recovered"] is False
    assert after["automatic_reference_reset"] is False


def test_all_healthy_values_do_not_certify_healthy_or_recovered():
    o = CausalTemporalQualityShadow(PIN)
    for t in range(40):
        result = observe(o, t)
    assert result["comparison_state"] == "PAIRED_UNVERIFIED_NUMERIC_OBSERVATION"
    assert result["quality_or_defocus_proven"] is False
    assert result["image_usable_verified"] is False
    assert result["trusted_reference_approved_by_this_module"] is False
    assert result["incident_closed_or_recovered"] is False


def test_constant_illumination_confound_preserved_but_numeric_trend_visible():
    o = CausalTemporalQualityShadow(PIN)
    for t in range(31):
        r = observe(
            o, t, sharpness=0.1 if t >= 30 else 1.0,
            hypothesis="ILLUMINATION_CONFOUNDED",
        )
    assert r["paired_numeric_ratios"]["sharpness"] == 0.1
    assert r["confounds"] == ["ILLUMINATION_UNRESOLVED"]
    assert r["quality_or_defocus_proven"] is False


def test_unknown_low_texture_abstains_without_suppression_or_recovery():
    o = CausalTemporalQualityShadow(PIN)
    for t in range(31):
        r = observe(o, t, 0.1 if t >= 30 else 1.0,
                    spatial="UNKNOWN_LOW_TEXTURE" if t == 30 else "SUFFICIENT_TILES")
    assert r["comparison_state"] == "UNKNOWN_LOW_TEXTURE_ABSTAIN"
    assert r["paired_numeric_ratios"] is None
    assert r["raw_scene_review_seen"] is False
    assert r["scene_warning_suppressed"] is False
    assert r["incident_closed_or_recovered"] is False


def test_unknown_past_anchor_cannot_be_laundered_into_health():
    o = CausalTemporalQualityShadow(PIN)
    for t in range(31):
        r = observe(o, t, spatial="UNKNOWN_LOW_TEXTURE" if t == 0 else "SUFFICIENT_TILES")
    assert r["comparison_state"] == "UNKNOWN_LOW_TEXTURE_ABSTAIN"


def test_unmeasured_spatial_does_not_pretend_to_be_sufficient():
    o = CausalTemporalQualityShadow(PIN)
    for t in range(31):
        r = observe(o, t, spatial="NOT_MEASURED")
    assert r["paired_numeric_ratios"]["sharpness"] == 1.0
    assert "SPATIAL_EVIDENCE_NOT_MEASURED" in r["confounds"]


def test_scene_warning_active_but_numeric_signal_never_clears_it():
    o = CausalTemporalQualityShadow(PIN)
    for t in range(31):
        r = observe(o, t, sharpness=0.2 if t == 30 else 1.0,
                    scene=(t == 0 or t == 30))
    assert "SCENE_REVIEW_ACTIVE_IN_PAIR" in r["confounds"]
    assert r["raw_scene_review_seen"] is True
    assert r["scene_warning_suppressed"] is False
    assert r["incident_closed_or_recovered"] is False


def test_gap_flushes_ephemeral_only_and_prevents_old_pair_use():
    o = CausalTemporalQualityShadow(PIN, max_gap_seconds=5.0)
    for t in range(4):
        observe(o, t)
    r = observe(o, 40)
    assert r["comparison_state"] == "DISCONTINUOUS_HISTORY"
    assert r["paired_numeric_ratios"] is None
    assert o.summary()["counters"]["discontinuous_history_gaps"] == 1
    assert o.summary()["reference_reenrollment"] is False


def test_strictly_increasing_time_and_pin_validation_are_transactional():
    o = CausalTemporalQualityShadow(PIN)
    observe(o, 1)
    with pytest.raises(ValueError, match="pixel identity"):
        observe(o, 2, pin="b" * 64)
    with pytest.raises(ValueError, match="increasing"):
        observe(o, 1)
    assert o.summary()["retained_numeric_observations"] == 1
    observe(o, 2)
    assert o.summary()["retained_numeric_observations"] == 2


def test_near_zero_anchor_abstains():
    o = CausalTemporalQualityShadow(PIN)
    for t in range(31):
        r = observe(o, t, sharpness=0.0 if t == 0 else 0.1)
    assert r["comparison_state"] == "NONINFORMATIVE_PAST_DENOMINATOR_ABSTAIN"
    assert r["paired_numeric_ratios"] is None


def test_reference_insufficient_current_abstains():
    o = CausalTemporalQualityShadow(PIN)
    for t in range(31):
        r = observe(
            o, t,
            hypothesis=("REFERENCE_TEXTURE_INSUFFICIENT" if t == 30
                        else "NO_SHARPNESS_LOSS_SIGNAL"),
        )
    assert r["comparison_state"] == "REFERENCE_TEXTURE_INSUFFICIENT_ABSTAIN"


def test_buffer_is_bounded_under_high_frequency():
    o = CausalTemporalQualityShadow(
        PIN, lookback_seconds=3, tolerance_seconds=0.1,
        max_gap_seconds=1, max_samples=8,
    )
    for i in range(250):
        observe(o, i / 10)
    summary = o.summary()
    assert summary["retained_numeric_observations"] <= 8
    assert summary["counters"]["capacity_evictions"] > 0
    assert summary["production_qualified"] is False


def test_no_implicit_rebaseline_under_persistent_defocus():
    o = CausalTemporalQualityShadow(PIN, lookback_seconds=10, tolerance_seconds=0.1)
    r = None
    for t in range(80):
        r = observe(o, t, sharpness=0.1 if t >= 20 else 1.0)
    assert r["paired_numeric_ratios"]["sharpness"] == 1.0
    # Ratio returning to one after prolonged degradation does NOT imply
    # camera recovery or human-authenticated healthy scene.
    assert r["image_usable_verified"] is False
    assert r["trusted_reference_approved_by_this_module"] is False
    assert r["incident_closed_or_recovered"] is False


@pytest.mark.parametrize("bad", [
    None, -0.1, float("nan"), float("inf"), True, "0.1",
])
def test_bad_numeric_quality_values_rejected_before_mutation(bad):
    o = CausalTemporalQualityShadow(PIN)
    doc = quality()
    doc["relative_sharpness"] = bad
    with pytest.raises(ValueError, match="quality measurement"):
        o.observe(
            time_s=0, reference_pixel_sha256=PIN, features=doc,
            spatial_evidence_status="SUFFICIENT_TILES", raw_scene_review=False,
        )
    assert o.summary()["retained_numeric_observations"] == 0


@pytest.mark.parametrize("alteration", [
    {"production_integration": True},
    {"blur_or_defocus_proven": True},
    {"image_usable_verified": True},
    {"automatic_recovery": True},
    {"detector_review_suppressed": True},
    {"status": "PRODUCTION_READY"},
])
def test_untrusted_or_promoted_feature_contract_rejected(alteration):
    o = CausalTemporalQualityShadow(PIN)
    doc = quality()
    doc.update(alteration)
    with pytest.raises(ValueError):
        o.observe(
            time_s=0, reference_pixel_sha256=PIN, features=doc,
            spatial_evidence_status="SUFFICIENT_TILES", raw_scene_review=False,
        )


@pytest.mark.parametrize("kwargs", [
    {"lookback_seconds": 0}, {"lookback_seconds": float("nan")},
    {"tolerance_seconds": 30}, {"tolerance_seconds": -1},
    {"max_gap_seconds": 0}, {"max_samples": 1}, {"max_samples": True},
    {"reference_pixel_sha256": "not-a-hash"},
])
def test_invalid_causal_configuration_rejected(kwargs):
    settings = {"reference_pixel_sha256": PIN}
    settings.update(kwargs)
    with pytest.raises(ValueError):
        CausalTemporalQualityShadow(**settings)
