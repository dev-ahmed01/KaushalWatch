"""Machine-checkable Camera Trust release ledger and fail-closed operational gate.

This is NOT a tamper detector. It audits pinned source continuity, complete
research-window feature extraction, independently generated cue comparisons,
and reproducible real labeled clip results. The production gate is blocked
until independent custody and held-out physical validation are furnished.
Never performs raw media transfer or incident mutation.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import tempfile

from .audit import audit_video_report
from .concordance import diagnose
from .clip_engine import VERSION as CLIP_VERSION, CATEGORIES
from .drive_sync import load_manifest

VERSION = 'KWTRUST_PRODUCT_ACCEPTANCE_V1'
EXPECTED_CLASSES = {'covered': 4, 'defocused': 4, 'moved': 4, 'normal': 2}
EXPECTED_CLIPS = 14


def sha_json(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def check(flag: bool, message: str) -> None:
    if not flag:
        raise ValueError(message)


def audit_clip_report(report: dict, approved_assets: list[dict], manifest_csv: Path) -> dict:
    """Require exact pinned Drive clip SHA, label and count integrity.

    The printed TP/FP/FN/TN are *against existing developmental annotations*;
    do not reuse this function to compute genuine physical event performance.
    """
    check(report.get('status') == CLIP_VERSION and
          report.get('production_qualified') is False and
          report.get('physical_camera_tampering_proven') is False and
          report.get('annotation_is_independent_custody') is False and
          report.get('held_out_camera_validation') is False and
          report.get('media_or_frames_exported') is False and
          report.get('new_operational_alerts_or_incidents_created') is False,
          'Clip report makes an unsupported field/production claim')
    check(report.get('source_manifest_sha256') == hashlib.sha256(manifest_csv.read_bytes()).hexdigest(),
          'Clip annotation manifest SHA mismatch')
    approved = {x['name'].removesuffix('.mp4'): x for x in approved_assets if x['group'] == 'clips'}
    clips = report.get('clips')
    check(len(approved) == EXPECTED_CLIPS and
          isinstance(clips, list) and len(clips) == EXPECTED_CLIPS and
          report.get('clips_evaluated') == EXPECTED_CLIPS and
          report.get('clips_expected') == EXPECTED_CLIPS and
          report.get('missing') == [], 'Expected all 14 source-labeled clips')
    seen = set(); classes = {}; total = {k: 0 for k in ('TP', 'FP', 'FN', 'TN')}
    samples = 0
    for clip in clips:
        name = clip.get('name')
        check(name in approved and name not in seen,
              'Duplicate, unapproved or unknown Drive clip')
        seen.add(name)
        check(clip.get('video_sha256') == approved[name]['sha256'],
              'SHA-256 of approved Drive clip differs from benchmark: '+name)
        check(clip.get('geometry_verified') is False and
              clip.get('physical_camera_health_verified') is False and
              clip.get('not_field_accuracy') is True and
              clip.get('source_is_independent_holdout') is False,
              'Clip ground truth overstated')
        cls = clip.get('annotation_class')
        check(cls in EXPECTED_CLASSES, 'Unknown event class')
        classes[cls] = classes.get(cls, 0)+1
        count = clip.get('numeric_count_table_vs_existing_annotations')
        check(isinstance(count, dict) and set(count) == set(total) and
              all(type(count[k]) is int and count[k] >= 0 for k in total),
              'Malformed clip event/nonevent accounting')
        trace = clip.get('trace')
        check(isinstance(trace, list) and len(trace) == clip.get('sampled_frames') and
              len(trace) > 0 and len(trace) <= 2000,
              'Missing/implausible clip trace')
        previous_frame = -1
        observed = {'TP':0, 'FP':0, 'FN':0, 'TN':0}
        for pos in trace:
            frame = pos.get('source_frame1')
            candidate = pos.get('research_candidate')
            is_event = pos.get('source_label_in_event')
            check(type(frame) is int and frame > previous_frame and
                  type(candidate) is bool and type(is_event) is bool and
                  pos.get('phase_displacement_is_physical_camera_truth') is False,
                  'Invalid, duplicated or overstated frame trace')
            previous_frame = frame
            observed['TP' if candidate and is_event else
                     'FP' if candidate else 'FN' if is_event else 'TN'] += 1
            for field in ('laplacian_ratio_to_initial_reference', 'brightness_delta',
                          'changed_tile_fraction', 'phase_registration_response',
                          'phase_normalized_shift_proxy'):
                value = pos.get(field)
                lower_bound = -1.0 if field == 'phase_registration_response' else 0.0
                check(type(value) in (float,int) and math.isfinite(value) and value >= lower_bound,
                      'Nonfinite or out-of-range numeric source feature')
        check(count == observed, 'Claimed candidate confusion counts differ from trace')
        samples += len(trace)
        for k in total: total[k] += count[k]
    check(classes == EXPECTED_CLASSES, 'Incomplete labeled clip class coverage')
    check(total == report.get('comparison_against_existing_development_annotations') and
          samples == report.get('sampled_frames'), 'Aggregated clip statistics differ from source traces')
    return {'clips': len(clips), 'samples': samples, 'classes': classes,
            'annotation_conditioned_numeric_counts': total,
            'approved_source_clip_shas_pinned': True,
            'independent_physical_truth': False}


def audit_external_scenes(report:dict) -> dict:
    """Audit non-labeled fixed-time numeric positions; never convert them to false alarms."""
    from .external_probe import STATUS
    check(report.get('status') == STATUS and
          report.get('source_camera_health_labels_independently_available') is False and
          report.get('held_out_positive_tamper_annotations_available') is False and
          report.get('field_false_alarm_rate_established') is False and
          report.get('production_qualified') is False and
          report.get('source_media_or_frames_exported') is False,
          'External sparse research evidence falsely asserts physical source health')
    videos=report.get('videos')
    check(isinstance(videos,list) and 1<=len(videos)<=16,
          'External comparison video count invalid')
    samples=candidates=unknown=0
    seen=set()
    for source in videos:
        name=source.get('file_name')
        check(isinstance(name,str) and name not in seen and
              source.get('status') == STATUS and
              source.get('source_video_has_independent_healthy_label') is False and
              source.get('camera_tampering_verified') is False and
              source.get('field_false_alarm_rate_established') is False and
              source.get('no_video_or_frames_exported') is True and
              isinstance(source.get('file_sha256'),str) and
              len(source['file_sha256'])==64,
              'Unverified external scene status or source identity mismatch')
        seen.add(name)
        seq=source.get('observations')
        check(isinstance(seq,list) and len(seq)==source.get('exact_decoded_samples')
              and len(seq)>0 and len(seq)<=1000,
              'External scene numeric positions missing')
        check(sum(bool(x.get('research_candidate')) for x in seq)==source.get('numerical_candidate_samples') and
              sum(not bool(x.get('geometric_registration_supported')) for x in seq)==source.get('unknown_geometry_samples') and
              all(x.get('physical_camera_pose_verified') is False for x in seq),
              'External scene confidence count/unknown geometry mismatch')
        samples+=len(seq)
        candidates+=source['numerical_candidate_samples']
        unknown+=source['unknown_geometry_samples']
    check(samples==report.get('total_frames_decoded') and
          candidates==report.get('total_numerical_candidate_positions') and
          unknown==report.get('total_unknown_geometry_positions'),
          'External scene aggregate candidate/missing counts differ')
    return {'unlabeled_context_videos':len(videos),'fixed_time_numeric_samples':samples,
            'numerical_candidates_not_confirmed_alerts':candidates,
            'geometry_unknown_samples':unknown,
            'healthy_camera_ground_truth':False,
            'field_false_alarm_rate_established':False}


def generate(r: dict, s: dict, video: dict, concordance: dict,
             clips: dict, drive_manifest: Path, clip_manifest_csv: Path,
             external_scenes:dict | None = None) -> dict:
    selection = audit_video_report(video, r, s)
    check(selection['selected_windows'] == 40 and
          selection['measured_video_windows'] == 40 and
          selection['unmeasured_video_windows'] == 0 and
          selection['measured_video_frames'] == 480,
          'Not all 40 selected controls have exactly the accepted 480 sparse video measurements')
    verified = diagnose(video, r, s)
    # Previously sampled evidence comparison is optional and was included in
    # the archived report. Re-derive all other values from the pinned sources.
    previous = concordance.get('previous_report_integrity', {})
    check(previous.get('provided') is False or
          (previous.get('provided') is True and
           previous.get('previous_scalar_evidence_reproduced') is True and
           previous.get('prior_measured_windows') == 20 and
           previous.get('prior_unmeasured_windows_now_sampled') == 20),
          'Archive must not make a false reproducibility claim')
    derived_stable = {k:v for k,v in verified.items() if k != 'previous_report_integrity'}
    saved_stable = {k:v for k,v in concordance.items() if k != 'previous_report_integrity'}
    check(saved_stable == derived_stable,
          'Cue-concordance artifact is stale or differs from rederived report')
    from_manifest = load_manifest(drive_manifest)
    clip_audit = audit_clip_report(clips, from_manifest, clip_manifest_csv)
    external_audit = audit_external_scenes(external_scenes) if external_scenes is not None else None
    assert len(verified['overall_concordance']) == 4
    # Only existing claims; this stage cannot invent external held-out evidence.
    blockers = [
        'No independent custody-verified video and field normal-hours evaluation',
        'No independently approved physical camera reference and enrollment process',
        'Gentle cover and camera-movement diagnostic recall unresolved',
        'Unverified scene-geometry proxies on 21 of 40 selected windows',
        'No prospective frozen-policy test across independent cameras, light, IR and motion',
        'Human authorization and privacy review required before live incidents/recovery',
    ]
    return {
        'status': VERSION,
        'software_readiness': 'COMPLETE_FOR_READ_ONLY_RESEARCH',
        'production_release': 'BLOCKED_REQUIRES_INDEPENDENT_FIELD_VALIDATION',
        'production_qualified': False,
        'automatic_camera_recovery_authorized': False,
        'threshold_or_policy_promoted_to_runtime': False,
        'physical_camera_health_truth_available': False,
        'source_continuity': {
            'phase3r_sha256': sha_json(r),
            'phase3s_sha256': sha_json(s),
            'video_feature_report_sha256': sha_json(video),
            'concordance_sha256': sha_json(concordance),
            'source_clip_report_sha256': sha_json(clips),
            'additional_unlabeled_scenes_sha256': sha_json(external_scenes) if external_scenes is not None else None,
        },
        'reproduced_research': {
            'selected_controls': 40,
            'selected_normal_labeled_hours': 2.0,
            'sparse_video_frames': 480,
            'three_consecutive_candidate_episode_starts': sum(
                day['policy_candidates']['sharpness_3_consecutive']['candidate_episode_starts']
                for day in video['by_day'].values()),
            'cue_comparison': verified['overall_concordance'],
            'geometry_unknown_windows': verified['geometric_coverage']['unknown_windows'],
            'drive_labeled_clips': clip_audit,
            'additional_unlabeled_scenes': external_audit,
        },
        'release_blockers': blockers,
        'source_media_exported': False,
        'human_or_camera_identity_inferred': False,
        'no_manual_report_upload_required_to_operate_workstation': True,
    }


def save_atomic(result: dict, output: Path) -> None:
    """Replace only this derived readiness summary, never the underlying evidence."""
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=output.parent,
                                         prefix='.readiness-', suffix='.tmp',
                                         delete=False) as stream:
            tmp = Path(stream.name)
            json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write('\n')
            stream.flush(); os.fsync(stream.fileno())
        os.replace(tmp, output)
    finally:
        if tmp is not None and tmp.exists(): tmp.unlink()
