"""Synthetic, privacy-preserving tests. These do not establish field accuracy."""
from __future__ import annotations
import numpy as np
from app.services.camera_quality import geometry, sample, tiles

def test_geometry_abstains_on_low_texture():
    flat=np.full((240,320,3),120,dtype=np.uint8)
    assert geometry(flat,flat)["state"]=="UNKNOWN_LOW_TEXTURE"
    assert sample(flat)["geometry"]["state"]=="UNKNOWN_NO_APPROVED_REFERENCE"

def test_brightness_dark_is_reviewable_but_not_qualified():
    dark=np.zeros((240,320,3),dtype=np.uint8)
    result=sample(dark)
    assert result["illumination"]=="TOO_DARK_PROXY"
    assert result["candidate_for_human_review"] is True
    assert result["production_qualified"] is False
    assert result["physical_camera_health"]=="UNKNOWN"

def test_sparse_identical_does_not_claim_frozen():
    frame=np.full((200,400,3),60,dtype=np.uint8)
    result=sample(frame,previous=frame)
    assert result["freeze"]["state"]=="IDENTICAL_SPARSE_SAMPLES"
    assert result["freeze"]["frozen_stream_proven"] is False

def test_tile_proxy_never_claims_partial_cover_as_truth():
    rng=np.random.default_rng(0)
    a=rng.integers(0,256,(256,256,3),dtype=np.uint8)
    b=a.copy()
    b[:128,:128]=90
    result=tiles(a,b)
    assert result["partial_cover_proven"] is False

def test_geometry_return_never_asserts_physical_movement():
    rng=np.random.default_rng(1)
    a=rng.integers(0,256,(256,256,3),dtype=np.uint8)
    r=geometry(a,a)
    assert r["state"] in {
        "UNKNOWN_FEW_KEYPOINTS","UNKNOWN_FEW_MATCHES",
        "UNKNOWN_REGISTRATION_FAILED","UNKNOWN_LOW_REGISTRATION_CONFIDENCE",
        "NO_LARGE_SCENE_DISPLACEMENT_OBSERVED",
    }
    assert r.get("physical_camera_movement_proven") is not True
