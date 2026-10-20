"""Conservative, explainable camera-quality *proxies*, not physical tamper truth.

No learned threshold fitting on the Day3/Day4 development source. Geometry
abstains on low texture, poor correspondence, or absent custodial reference.
Sampling is sparse and offline; timestamp correctness is reported separately.
"""
from __future__ import annotations
import cv2
import numpy as np

def gray(frame: np.ndarray) -> np.ndarray:
    if frame is None or frame.size == 0:
        raise ValueError("Empty decoded frame")
    if frame.ndim == 3:
        return cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
    if frame.ndim == 2:
        return frame
    raise ValueError("Unsupported frame")

def scaled(frame: np.ndarray, width: int=480) -> np.ndarray:
    im=gray(frame)
    if im.shape[1] > width:
        im=cv2.resize(im,(width,max(32,round(im.shape[0]*width/im.shape[1]))))
    return im.astype(np.uint8)

def geometry(reference: np.ndarray, current: np.ndarray) -> dict:
    """ORB+RANSAC proxy. Low confidence returns UNKNOWN rather than stationary."""
    ref=scaled(reference); now=scaled(current)
    if ref.shape != now.shape:
        return {"state":"UNKNOWN_REFERENCE_DIMENSIONS","inliers":0}
    if cv2.Laplacian(ref,cv2.CV_64F).var() < 20 or cv2.Laplacian(now,cv2.CV_64F).var() < 12:
        return {"state":"UNKNOWN_LOW_TEXTURE","inliers":0}
    orb=cv2.ORB_create(nfeatures=900)
    kp1,d1=orb.detectAndCompute(ref,None)
    kp2,d2=orb.detectAndCompute(now,None)
    if d1 is None or d2 is None or len(kp1)<18 or len(kp2)<18:
        return {"state":"UNKNOWN_FEW_KEYPOINTS","inliers":0}
    matches=cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(d1,d2,k=2)
    chosen=[m for pair in matches if len(pair)==2 for m,n in [pair] if m.distance<0.72*n.distance]
    if len(chosen)<16:
        return {"state":"UNKNOWN_FEW_MATCHES","inliers":len(chosen)}
    a=np.float32([kp1[m.queryIdx].pt for m in chosen])
    b=np.float32([kp2[m.trainIdx].pt for m in chosen])
    matrix,inlier=cv2.estimateAffinePartial2D(
        a,b,method=cv2.RANSAC,ransacReprojThreshold=3,maxIters=1500,
        confidence=.99)
    if matrix is None or inlier is None:
        return {"state":"UNKNOWN_REGISTRATION_FAILED","inliers":0}
    count=int(inlier.sum());frac=count/len(chosen)
    if count<12 or frac<0.45:
        return {"state":"UNKNOWN_LOW_REGISTRATION_CONFIDENCE","inliers":count}
    dx=float(matrix[0,2])/ref.shape[1]
    dy=float(matrix[1,2])/ref.shape[0]
    displacement=float(np.hypot(dx,dy))
    # Geometric movement remains a proxy: parallax or a moved scene can mimic it.
    state="POSSIBLE_SCENE_DISPLACEMENT" if displacement>0.035 else "NO_LARGE_SCENE_DISPLACEMENT_OBSERVED"
    return {"state":state,"inliers":count,"inlier_ratio":round(frac,4),
            "normalized_translation":round(displacement,5),
            "physical_camera_movement_proven":False}

def tiles(reference: np.ndarray, current: np.ndarray, grid: int=8) -> dict:
    ref=scaled(reference);now=scaled(current)
    if ref.shape != now.shape:return {"state":"UNKNOWN_DIMENSIONS"}
    h,w=ref.shape; h=h//grid*grid;w=w//grid*grid
    aa=ref[:h,:w].reshape(grid,h//grid,grid,w//grid).transpose(0,2,1,3)
    bb=now[:h,:w].reshape(grid,h//grid,grid,w//grid).transpose(0,2,1,3)
    dif=np.mean(np.abs(aa.astype(np.float32)-bb.astype(np.float32)),axis=(2,3))
    grad_a=np.mean(np.abs(np.diff(aa.astype(np.float32),axis=3)),axis=(2,3))
    grad_b=np.mean(np.abs(np.diff(bb.astype(np.float32),axis=3)),axis=(2,3))
    changed=(dif>28)
    flattened=(grad_b < np.maximum(grad_a*0.40,1.5))
    local=np.logical_and(changed,flattened)
    local_fraction=float(local.mean())
    uniform_fraction=float(changed.mean())
    state=("POSSIBLE_LOCAL_OBSTRUCTION" if .08<=local_fraction<=.70
           and uniform_fraction<.85 else "NO_DISTINCT_LOCAL_CHANGE_OBSERVED")
    return {"state":state,"changed_tile_fraction":round(uniform_fraction,4),
            "flattened_changed_tile_fraction":round(local_fraction,4),
            "partial_cover_proven":False}

def split_evidence_decision(*, illumination: str, focus: dict,
                            geometry: dict, localized_coverage: dict,
                            freeze: dict, reference_present: bool) -> dict:
    """Separate visual evidence usability from suspected scene interference.

    Interpret existing conservative visual cues only. No detector training,
    source authentication, behavioural intent attribution or threshold tuning.
    Sparse identical samples do not establish a replayed stream.
    """
    obscured = localized_coverage.get("state") == "POSSIBLE_LOCAL_OBSTRUCTION"
    displaced = geometry.get("state") == "POSSIBLE_SCENE_DISPLACEMENT"
    defocused = focus.get("state") == "POSSIBLE_DEFOCUS"
    illumination_bad = illumination in {"TOO_DARK_PROXY", "OVEREXPOSED_PROXY"}
    uncertain_reference = not reference_present
    unknown_registration = geometry.get("state", "").startswith("UNKNOWN_")
    if illumination_bad or defocused or obscured:
        usability = "NOT_USABLE_FOR_VISUAL_VERIFICATION"
        usable_reason = ("VISIBILITY_DEGRADED" if illumination_bad
                         else "FOCUS_DEGRADED" if defocused else "LOCAL_VIEW_OBSCURED")
    elif displaced:
        usability = "REVIEW_REQUIRED_SCENE_ALIGNMENT"
        usable_reason = "REFERENCE_SCENE_CHANGED"
    elif uncertain_reference:
        usability = "UNKNOWN_NO_REFERENCE"
        usable_reason = "REFERENCE_REQUIRED"
    elif unknown_registration:
        usability = "UNKNOWN_SCENE_REGISTRATION"
        usable_reason = "NO_RELIABLE_SCENE_MATCH"
    else:
        usability = "PROVISIONALLY_OBSERVABLE"
        usable_reason = "NO_SEVERE_QUALITY_LOSS_OBSERVED"
    if reference_present and (obscured or displaced):
        interference = "POSSIBLE_SCENE_INTERFERENCE_REVIEW"
    elif not reference_present:
        interference = "UNKNOWN_NO_REFERENCE"
    else:
        interference = "NOT_ESTABLISHED"
    # The present reference is *not* independently authenticated by pixels.
    # No "true camera state" inference is possible even for clear video.
    return {
        "schema": "KW_CAMERA_EVIDENCE_TRIAGE_V1",
        "usability": usability,
        "usability_reason": usable_reason,
        "interference_review": interference,
        "quality_loss_without_interference_attribution":
            bool((illumination_bad or defocused) and not (obscured or displaced)),
        "sparse_identical_frames_observed":
            freeze.get("state") == "IDENTICAL_SPARSE_SAMPLES",
        "reference_status":
            "PRESENT_CUSTODY_NOT_ATTESTED_BY_PIXELS" if reference_present
            else "ABSENT",
        "hold_attendance_and_practical_claims":
            usability != "PROVISIONALLY_OBSERVABLE",
        "review_required":
            usability != "PROVISIONALLY_OBSERVABLE" or
            interference != "NOT_ESTABLISHED",
        "physical_camera_health": "UNKNOWN",
        "malicious_tampering_proven": False,
        "enforcement_authorized": False,
        "institutional_accuracy_qualified": False,
    }


def sample(frame: np.ndarray, reference: np.ndarray | None=None,
           previous: np.ndarray | None=None) -> dict:
    im=scaled(frame)
    lum=float(im.mean());bright=float((im>=248).mean())
    sharp=float(cv2.Laplacian(im,cv2.CV_64F).var())
    illumination=("TOO_DARK_PROXY" if lum<25 else
                  "OVEREXPOSED_PROXY" if lum>235 and bright>.8 else
                  "NO_EXTREME_ILLUMINATION_OBSERVED")
    freeze={"state":"UNKNOWN_NO_PREVIOUS_SAMPLE"}
    if previous is not None:
        prev=scaled(previous)
        if prev.shape==im.shape:
            equal=np.array_equal(prev,im)
            freeze={"state":"IDENTICAL_SPARSE_SAMPLES" if equal else "NONIDENTICAL_SPARSE_SAMPLES",
                    "frozen_stream_proven":False}
        else:freeze={"state":"UNKNOWN_DIMENSIONS"}
    geo={"state":"UNKNOWN_NO_APPROVED_REFERENCE"}
    local={"state":"UNKNOWN_NO_APPROVED_REFERENCE"}
    focus={"state":"UNKNOWN_NO_APPROVED_REFERENCE"}
    if reference is not None:
        ref=scaled(reference)
        geo=geometry(ref,im)
        local=tiles(ref,im)
        refsharp=float(cv2.Laplacian(ref,cv2.CV_64F).var())
        focus={"state":("POSSIBLE_DEFOCUS" if refsharp>=20 and sharp/refsharp<0.42
                        else "UNKNOWN_LOW_REFERENCE_TEXTURE" if refsharp<20
                        else "NO_SIGNIFICANT_SHARPNESS_DROP_OBSERVED"),
               "sharpness_ratio":round(sharp/max(refsharp,1e-6),4)}
    triage=split_evidence_decision(
        illumination=illumination, focus=focus, geometry=geo,
        localized_coverage=local, freeze=freeze,
        reference_present=reference is not None,
    )
    possible=any(v.get("state","").startswith("POSSIBLE") for v in (geo,local,focus))
    possible=possible or illumination in ("TOO_DARK_PROXY","OVEREXPOSED_PROXY")
    return {"illumination":illumination,"brightness":round(lum,2),
            "laplacian_variance":round(sharp,3),"focus":focus,"geometry":geo,
            "localized_coverage":local,"freeze":freeze,
            "candidate_for_human_review":possible,
            "evidence_triage":triage,
            "physical_camera_health":"UNKNOWN","production_qualified":False}
