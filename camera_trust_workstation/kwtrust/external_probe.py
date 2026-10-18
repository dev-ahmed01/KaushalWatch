"""Sparse unbiased-time external scene probe on UNANNOTATED video (research only).

Samples fixed wallclock recording-relative positions *before seeing model cues*.
Never assumes a recording is healthy/compromised. No media, image crops or
person-identifying data are exported or retained in the report.
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path

import cv2
import numpy as np

from .clip_engine import _prep, _tiles

STATUS='KWTRUST_EXTERNAL_SCENE_PROBE_UNLABELED_V1'


def sha256_file(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(8*1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def probe(path:Path, *,sample_interval_seconds:float=5.0, max_samples:int=120)->dict:
    if sample_interval_seconds < 1 or sample_interval_seconds > 60 or type(max_samples) is not int or max_samples < 4 or max_samples > 1000:
        raise ValueError('Fixed coverage parameters out of range')
    path=Path(path)
    cap=cv2.VideoCapture(str(path))
    if not cap.isOpened():raise ValueError('Source AVI decoder unavailable')
    fps=float(cap.get(cv2.CAP_PROP_FPS)); frames=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if not (math.isfinite(fps) and 1<=fps<=120 and frames>0 and frames<=5_000_000):
        cap.release();raise ValueError('Invalid unannotated source metadata')
    step=max(1,round(fps*sample_interval_seconds))
    targets=list(range(0,frames,step))[:max_samples]
    observations=[];reference=None;prev=None;skipped=[]
    try:
        for target in targets:
            if not cap.set(cv2.CAP_PROP_POS_FRAMES,target):
                skipped.append(target+1);continue
            ok,bgr=cap.read()
            if not ok or bgr is None:
                skipped.append(target+1);continue
            decoder_position=cap.get(cv2.CAP_PROP_POS_FRAMES)
            if not math.isfinite(decoder_position) or abs(decoder_position-(target+1))>.51:
                skipped.append(target+1);continue
            gray=_prep(bgr)
            lap=float(cv2.Laplacian(gray,cv2.CV_64F).var())
            mean=float(gray.mean())
            if reference is None:reference=gray.copy()
            if prev is None:prev=gray.copy()
            base_lap=float(cv2.Laplacian(reference,cv2.CV_64F).var())
            blur_proxy=base_lap>=2 and lap/max(base_lap,1e-6)<.45
            local_fraction=_tiles(reference,gray)
            brightness=abs(mean-float(reference.mean()))
            global_proxy=local_fraction>.70 and brightness>7
            # Phase correlation of derivative images is unreliable on many
            # featureless scenes. Preserve unknown explicitly.
            gr=cv2.Laplacian(reference.astype(np.float32),cv2.CV_32F)
            gc=cv2.Laplacian(gray.astype(np.float32),cv2.CV_32F)
            hann=cv2.createHanningWindow((gr.shape[1],gr.shape[0]),cv2.CV_32F)
            (dx,dy),confidence=cv2.phaseCorrelate(gr,gc,hann)
            norm=float(math.hypot(dx,dy)/math.hypot(*gr.shape)) if all(math.isfinite(v) for v in (dx,dy)) else None
            geometry_known=math.isfinite(confidence) and confidence>=.2 and norm is not None
            observations.append({
                'source_frame1':target+1,
                'recording_relative_second':round(target/fps,3),
                'sharpness_ratio_to_first_sample':round(lap/max(base_lap,1e-6),5),
                'mean_luma_change_to_initial':round(brightness,4),
                'changed_tile_fraction':round(local_fraction,4),
                'blur_proxy':bool(blur_proxy),
                'global_visual_change_proxy':bool(global_proxy),
                'research_candidate':bool(blur_proxy or global_proxy),
                'geometric_registration_supported':bool(geometry_known),
                'phase_shift_proxy':round(norm,5) if geometry_known else None,
                'physical_camera_pose_verified':False,
            })
            prev=gray
    finally:
        cap.release()
    if not observations:raise ValueError('No exact source frames sampled')
    return {
        'file_name':path.name,
        'status':STATUS,
        'file_sha256':sha256_file(path),
        'source_file_bytes':path.stat().st_size,
        'source_frame_count':frames,
        'source_fps':fps,
        'duration_seconds':round(frames/fps,3),
        'fixed_sampling_interval_seconds':sample_interval_seconds,
        'planned_sample_count':len(targets),
        'exact_decoded_samples':len(observations),
        'missing_frame_indices':skipped,
        'numerical_candidate_samples':sum(o['research_candidate'] for o in observations),
        'blur_proxy_samples':sum(o['blur_proxy'] for o in observations),
        'global_change_proxy_samples':sum(o['global_visual_change_proxy'] for o in observations),
        'unknown_geometry_samples':sum(not o['geometric_registration_supported'] for o in observations),
        'predeclared_selection_independent_of_model_scores':True,
        'source_video_has_independent_healthy_label':False,
        'camera_tampering_verified':False,
        'field_false_alarm_rate_established':False,
        'no_video_or_frames_exported':True,
        'observations':observations,
    }


def run(video_paths:list[Path],out:Path,*,interval:float=5.0,max_samples:int=120):
    if out.exists():raise FileExistsError('Research result path already used')
    if len(video_paths)<1 or len(video_paths)>16:raise ValueError('Invalid number of scene sources')
    reports=[probe(p,sample_interval_seconds=interval,max_samples=max_samples) for p in video_paths]
    result={
        'status':STATUS,
        'source_camera_health_labels_independently_available':False,
        'held_out_positive_tamper_annotations_available':False,
        'field_false_alarm_rate_established':False,
        'production_qualified':False,
        'videos':reports,
        'total_fixed_positions_requested':sum(x['planned_sample_count'] for x in reports),
        'total_frames_decoded':sum(x['exact_decoded_samples'] for x in reports),
        'total_numerical_candidate_positions':sum(x['numerical_candidate_samples'] for x in reports),
        'total_unknown_geometry_positions':sum(x['unknown_geometry_samples'] for x in reports),
        'source_media_or_frames_exported':False,
    }
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('x',encoding='utf-8') as f:
        json.dump(result,f,indent=2,sort_keys=True,allow_nan=False);f.write('\n')
    return result
