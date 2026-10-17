"""Offline-only structural/photometric cause measurements; no detector tuning."""
from __future__ import annotations

import cv2
import numpy as np
import pytest

from app.services.camera_scene_cause_shadow import (
    SceneCauseDiagnostics, PHASE_PRESETS,
)
from app.services.camera_spatial_scene_shadow import _small, spatial_metrics


@pytest.fixture
def reference():
    rng=np.random.default_rng(17)
    image=rng.integers(45,151,size=(144,192),dtype=np.uint8)
    image=cv2.GaussianBlur(image,(3,3),0.65)
    return cv2.cvtColor(image,cv2.COLOR_GRAY2BGR)


def analyze(reference,current):
    status=spatial_metrics(_small(reference),current)["evidence_status"]
    return SceneCauseDiagnostics(_small(reference)).inspect(
        current,spatial_evidence_status=status,
    )


def test_immutable_reference_and_no_change_does_not_claim_motion(reference):
    ref=_small(reference)
    checker=SceneCauseDiagnostics(ref)
    ref[:]=0  # Later caller mutation cannot alter the fixed reference.
    result=checker.inspect(reference,spatial_evidence_status="SUFFICIENT_TILES")
    assert result["camera_movement_proven"] is False
    assert result["reference_updated"] is False
    assert result["suppresses_raw_review"] is False
    assert result["production_integration"] is False
    assert result["translation_preset_sweep"]["conservative"][
        "candidate_global_translation_supported"
    ] is False


def test_global_lighting_change_is_hypothesis_not_a_suppression(reference):
    brighter=cv2.add(reference,np.full_like(reference,55))
    result=analyze(reference,brighter)
    assert result["spatial_evidence_status"]=="SUFFICIENT_TILES"
    assert result["median_brightness_delta"]>=40
    assert "PHOTOMETRIC_SHIFT_COMPATIBLE" in result["hypotheses"]
    assert result["suppresses_raw_review"] is False
    assert result["evidence_usable_verified"] is False


def test_one_region_foreground_perturbation_is_not_movement_proof(reference):
    intruder=reference.copy()
    rng=np.random.default_rng(882)
    intruder[:72,:96]=rng.integers(20,220,(72,96,3),dtype=np.uint8)
    result=analyze(reference,intruder)
    assert result["changed_tiles"]>0
    assert result["changed_quadrants"]<=2
    assert "LOCAL_FOREGROUND_OR_OCCLUSION_COMPATIBLE" in result["hypotheses"]
    assert result["camera_movement_proven"] is False


def test_low_texture_is_explicitly_unknown_not_recovery(reference):
    black=np.zeros_like(reference)
    status=spatial_metrics(_small(reference),black)["evidence_status"]
    assert status=="UNKNOWN_LOW_TEXTURE"
    result=SceneCauseDiagnostics(_small(reference)).inspect(
        black,spatial_evidence_status=status,
    )
    assert "STRUCTURAL_EVIDENCE_INSUFFICIENT" in result["hypotheses"]
    assert not result["evidence_usable_verified"]


def test_coherent_translation_is_compatible_not_confirmed_cause(reference):
    warped=cv2.warpAffine(
        reference,np.float32([[1,0,6],[0,1,4]]),
        (192,144),borderMode=cv2.BORDER_REFLECT,
    )
    result=analyze(reference,warped)
    dx,dy=result["global_phase_translation_pixels"]
    assert abs(dx-6)<1.5
    assert abs(dy-4)<1.5
    assert result["translation_preset_sweep"]["exploratory"]["quadrants_agreeing"]>=3
    assert result["camera_movement_proven"] is False
    assert result["reference_updated"] is False


@pytest.mark.parametrize("bad",[
    None, np.zeros((144,192),dtype=np.float32),
    np.zeros((144,191),dtype=np.uint8),
])
def test_unapproved_or_incorrect_reference_shape_rejected(bad):
    with pytest.raises(ValueError,match="Fixed"):
        SceneCauseDiagnostics(bad)


def test_mismatched_detector_evidence_aborts_without_result(reference):
    observer=SceneCauseDiagnostics(_small(reference))
    with pytest.raises(ValueError,match="mismatch"):
        observer.inspect(reference,spatial_evidence_status="UNKNOWN_LOW_TEXTURE")


def test_presets_are_diagnostic_only_not_detector_thresholds():
    assert set(PHASE_PRESETS)=={"conservative","exploratory"}
    for floor,agree,tolerance in PHASE_PRESETS.values():
        assert 0<floor<1
        assert agree>=3
        assert tolerance<=3
