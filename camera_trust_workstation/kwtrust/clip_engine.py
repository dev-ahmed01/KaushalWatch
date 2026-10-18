"""Offline camera-quality diagnostic benchmark on explicitly labeled short clips.

Requires source clips (never bundled or served) and a selected_clips.csv from
Drive. Assesses VISUAL FEATURE CHANGES, not malign intent or physical custody.
No model fitting; frozen illustrative rules; keeps frame traces numeric only.
"""
from __future__ import annotations
import csv
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

VERSION = 'KWTRUST_CLIP_DIAGNOSTICS_V1_NONOPERATIONAL'
CATEGORIES = {'0': 'normal', '1': 'covered', '2': 'defocused', '3': 'moved'}


def verify_manifest(path: Path) -> list[dict]:
    with path.open(newline='', encoding='utf-8-sig') as f:
        rows=list(csv.DictReader(f))
    assert rows and len(rows)<=1000, 'Missing or implausibly large annotation manifest'
    seen=set()
    for r in rows:
        assert r['class'] in CATEGORIES and r['label']==CATEGORIES[r['class']], 'Unexpected label'
        assert r['name'] and r['name'] not in seen and r['name'].replace('_','').isalnum(), 'Invalid or duplicate name'
        seen.add(r['name'])
        for field in ('event_start_frame','event_end_frame','clip_start_frame0','clip_end_frame0'):
            assert r[field].isdigit(), 'Invalid annotated frame'
        assert int(r['event_start_frame'])<=int(r['event_end_frame'])
        assert int(r['clip_start_frame0'])<=int(r['clip_end_frame0'])
        assert r['selection'] in ('gentle','strong','normal'), 'Unexpected stratum'
    return rows


def _prep(frame):
    gray=cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    h,w=gray.shape
    gray=cv2.resize(gray,(320,max(32,round(h*320/w))),interpolation=cv2.INTER_AREA).astype(np.uint8)
    return gray


def _tiles(a: np.ndarray,b: np.ndarray,grid=8):
    h,w=a.shape
    hh=h//grid;ww=w//grid
    a=a[:hh*grid,:ww*grid].reshape(grid,hh,grid,ww).transpose(0,2,1,3)
    b=b[:hh*grid,:ww*grid].reshape(grid,hh,grid,ww).transpose(0,2,1,3)
    dif=np.abs(a.astype(np.float32)-b.astype(np.float32)).mean(axis=(2,3))
    return float((dif>20).mean())


def evaluate_clip(path: Path, annotation: dict, *, reference: np.ndarray | None=None, stride: int=3)->dict:
    """Sample every stride frames (1 FPS for 3 FPS source), bounded to AVI segment.

    Reference is pre-event portion of matching onset clip, supplied unchanged
    to recovery clip of SAME annotated event. No future lookahead online claim.
    """
    assert 1<=stride<=30
    cap=cv2.VideoCapture(str(path))
    if not cap.isOpened():raise ValueError('Cannot read source clip: '+path.name)
    n=int(cap.get(cv2.CAP_PROP_FRAME_COUNT));fps=float(cap.get(cv2.CAP_PROP_FPS))
    if not (1<=n<=100000 and 0<fps<=120):raise ValueError('Invalid clip metadata')
    raw_frames=[]
    try:
        for j in range(n):
            ok,fr=cap.read()
            if not ok:break
            if j%stride==0:raw_frames.append((j,_prep(fr)))
    finally:cap.release()
    if len(raw_frames)<4:raise ValueError('Insufficient frames')
    if reference is None:
        # Only allowed on onset (with a visible pre-event interval) or normal.
        pre=[gray for i,gray in raw_frames if
             int(annotation['clip_start_frame0'])+i+1 < int(annotation['event_start_frame'])]
        if annotation['class']!='0' and len(pre)<4:
            raise ValueError('No genuine pre-event reference; matching onset clip required')
        reference=np.median(np.stack(pre[:12] or [g for _,g in raw_frames[:4]]),axis=0).astype(np.uint8)
    reference_lap=float(cv2.Laplacian(reference,cv2.CV_64F).var())
    ref_mean=float(reference.mean())
    ref_grad=cv2.Laplacian(reference.astype(np.float32),cv2.CV_32F)
    hanning=cv2.createHanningWindow((reference.shape[1],reference.shape[0]),cv2.CV_32F)
    trace=[]
    for i,gray in raw_frames:
        lap=float(cv2.Laplacian(gray,cv2.CV_64F).var())
        blur_ratio=lap/max(reference_lap,1e-6)
        brightness_delta=abs(float(gray.mean())-ref_mean)
        frac=_tiles(reference,gray)
        current_grad=cv2.Laplacian(gray.astype(np.float32),cv2.CV_32F)
        (dx,dy),phase_response=cv2.phaseCorrelate(ref_grad,current_grad,hanning)
        diagonal=float(np.hypot(*reference.shape))
        phase_shift=float(np.hypot(dx,dy)/diagonal)
        if not np.isfinite(phase_response) or not np.isfinite(phase_shift):
            phase_state='UNKNOWN_UNRELIABLE_REGISTRATION'
            phase_response=0.0
            phase_shift=0.0
        elif phase_response<.20:
            phase_state='UNKNOWN_LOW_REGISTRATION_CONFIDENCE'
        elif phase_shift>.06:
            phase_state='POSSIBLE_GLOBAL_SHIFT_NOT_PHYSICAL_TRUTH'
        else:
            phase_state='NO_LARGE_REGISTERED_SHIFT_OBSERVED'
        local_patch_proxy=bool(.20<=frac<=.65 and blur_ratio>2.0)
        # Conservative generic cues; NOT detector/camera-tamper thresholds.
        blur=(reference_lap>=2 and blur_ratio<0.45)
        changed=(frac>0.70 and brightness_delta>7)
        # Scene geometry is UNKNOWN here, never inferred from frame difference.
        quality_numeric=bool(blur or changed)
        original=int(annotation['clip_start_frame0'])+i+1
        annotated=(annotation['class']!='0' and
                   int(annotation['event_start_frame'])<=original<=int(annotation['event_end_frame']))
        trace.append({'sample_local_frame0':i,'source_frame1':original,
                      'source_label_in_event':annotated,
                      'laplacian_ratio_to_initial_reference':round(blur_ratio,5),
                      'brightness_delta':round(brightness_delta,4),
                      'changed_tile_fraction':round(frac,4),
                      'blur_proxy':bool(blur),'global_change_proxy':bool(changed),
                      'research_candidate':quality_numeric,
                      'geometry':'UNKNOWN_NOT_ESTABLISHED',
                      'phase_registration_response':round(float(phase_response),4),
                      'phase_normalized_shift_proxy':round(float(phase_shift),5),
                      'phase_shift_status':phase_state,
                      'localized_change_proxy':local_patch_proxy,
                      'phase_displacement_is_physical_camera_truth':False})
    tp=sum(x['research_candidate'] and x['source_label_in_event'] for x in trace)
    fp=sum(x['research_candidate'] and not x['source_label_in_event'] for x in trace)
    fn=sum(not x['research_candidate'] and x['source_label_in_event'] for x in trace)
    tn=sum(not x['research_candidate'] and not x['source_label_in_event'] for x in trace)
    return ({'name':annotation['name'],'annotation_class':annotation['label'],
             'selection':annotation['selection'], 'video_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
             'frames_in_source':n,'fps':fps,'sampled_frames':len(trace),'reference_laplacian_variance':round(reference_lap,4),
             'numeric_count_table_vs_existing_annotations':{'TP':tp,'FP':fp,'FN':fn,'TN':tn},
             'any_candidate':any(x['research_candidate'] for x in trace),
             'geometry_verified':False,'physical_camera_health_verified':False,
             'exploratory_localized_change_samples':sum(x['localized_change_proxy'] for x in trace),
             'exploratory_registered_global_shift_samples':sum(
                 x['phase_shift_status']=='POSSIBLE_GLOBAL_SHIFT_NOT_PHYSICAL_TRUTH' for x in trace),
             'unreliable_geometric_registration_samples':sum(
                 x['phase_shift_status'].startswith('UNKNOWN_') for x in trace),
             'not_field_accuracy':True,'source_is_independent_holdout':False,
             'trace':trace},reference)


def evaluate_directory(manifest: Path, clips: Path, out: Path, *,stride=3)->dict:
    if out.exists():raise FileExistsError('Research report already exists; refusing to overwrite')
    rows=verify_manifest(manifest)
    results=[]; refs={}; missing=[]
    # Onsets precede recoveries regardless of manifest order.
    rows=sorted(rows,key=lambda r:('recovery' in r['name'],r['name']))
    for r in rows:
        path=clips/(r['name']+'.mp4')
        if not path.is_file():
            missing.append(r['name']);continue
        family=r['name'].rsplit('_',1)[0]
        recovery=r['name'].endswith('_recovery')
        if recovery and family not in refs:
            missing.append('matching_onset_reference:'+r['name']);continue
        result,ref=evaluate_clip(path,r,reference=refs.get(family),stride=stride)
        if not recovery:refs[family]=ref
        results.append(result)
    total={k:sum(x['numeric_count_table_vs_existing_annotations'][k] for x in results)
           for k in ('TP','FP','FN','TN')}
    answer={'status':VERSION,'source_manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest(),
            'clips_evaluated':len(results),'clips_expected':len(rows),'missing':missing,
            'sampled_frames':sum(x['sampled_frames'] for x in results),
            'comparison_against_existing_development_annotations':total,
            'quality_rules_are_exploratory_frozen_in_source':True,
            'research_only':True,'production_qualified':False,'physical_camera_tampering_proven':False,
            'held_out_camera_validation':False,'annotation_is_independent_custody':False,
            'new_operational_alerts_or_incidents_created':False,
            'media_or_frames_exported':False,'clips':results}
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('x',encoding='utf-8') as fd:json.dump(answer,fd,indent=2,allow_nan=False)
    return answer
