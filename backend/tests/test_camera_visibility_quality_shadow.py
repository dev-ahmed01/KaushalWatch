"""Synthetic sharpness, brightness, texture and privacy regressions."""
import cv2
import numpy as np
import pytest

from app.services.camera_visibility_quality_shadow import VisibilityQualityShadow


def structured(seed=121):
    rng=np.random.default_rng(seed)
    gray=rng.integers(35,145,(144,192),dtype=np.uint8)
    return cv2.cvtColor(gray,cv2.COLOR_GRAY2BGR)


def test_blur_is_compatible_without_proof_or_suppressing_scene_change():
    source=structured()
    probe=VisibilityQualityShadow.from_bgr(source)
    blurred=cv2.GaussianBlur(source,(17,17),4)
    measured=probe.inspect(blurred)
    assert measured["quality_hypothesis"]=="SHARPNESS_LOSS_COMPATIBLE"
    assert measured["relative_sharpness"]<0.35
    assert measured["relative_edge_fraction"]<0.65
    assert measured["blur_or_defocus_proven"] is False
    assert measured["image_usable_verified"] is False
    assert measured["detector_review_suppressed"] is False
    assert measured["automatic_recovery"] is False
    assert measured["production_integration"] is False


def test_unmodified_reference_is_not_declared_defocused():
    reference=structured()
    probe=VisibilityQualityShadow.from_bgr(reference)
    result=probe.inspect(reference)
    assert result["quality_hypothesis"]=="NO_SHARPNESS_LOSS_SIGNAL"
    assert 0.98<result["relative_sharpness"]<1.02
    assert result["image_usable_verified"] is False


def test_brightness_shift_is_confound_not_defocus_verdict():
    reference=structured()
    probe=VisibilityQualityShadow.from_bgr(reference)
    shifted=cv2.add(reference,np.full_like(reference,80))
    result=probe.inspect(shifted)
    assert result["quality_hypothesis"]=="ILLUMINATION_CONFOUNDED"
    assert result["median_brightness_shift"]>=45
    assert not result["blur_or_defocus_proven"]


def test_low_detail_source_abstains_instead_of_claiming_defocus():
    empty=np.full((144,192,3),110,dtype=np.uint8)
    probe=VisibilityQualityShadow.from_bgr(empty)
    result=probe.inspect(cv2.GaussianBlur(empty,(15,15),3))
    assert result["quality_hypothesis"]=="REFERENCE_TEXTURE_INSUFFICIENT"
    assert result["image_usable_verified"] is False


def test_reference_is_copy_not_mutated_by_external_owner():
    ref=structured()
    probe=VisibilityQualityShadow.from_bgr(ref)
    old=probe.inspect(ref)
    ref[:]=0
    new=probe.inspect(structured())
    assert old["quality_hypothesis"]==new["quality_hypothesis"]
    assert old["reference_laplacian_variance"]==new["reference_laplacian_variance"]


@pytest.mark.parametrize("bad",[
    None,np.zeros((144,192),dtype=np.uint8),
    np.zeros((144,192,4),dtype=np.uint8),
    np.zeros((144,192,3),dtype=np.float32),
])
def test_rejects_malformed_bgr(bad):
    with pytest.raises(ValueError):
        VisibilityQualityShadow.from_bgr(bad)
