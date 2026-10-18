"""Strict independent accounting of an exported Camera Trust research report.

Checks source identity, exact selection and video-feature coverage. Does not
infer physical camera health, attack detection, or field false-positive rates.
Input reports are JSON-only and never load original videos or expose frames.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
from typing import Any

from .analysis import DAYS, EvidenceError, build_report, parse_reports, require

SUPPORTED_VIDEO_STATUSES = {
    'UNVERIFIED_LOCAL_VIDEO_FEATURES_NOT_GROUND_TRUTH',
    'SOURCE_VIDEO_NOT_MOUNTED', # legacy: was also used for budget skips
    'NOT_SELECTED_FOR_BOUNDED_VIDEO_SAMPLING',
}
MEASURED = 'UNVERIFIED_LOCAL_VIDEO_FEATURES_NOT_GROUND_TRUTH'
MISSING = 'SOURCE_VIDEO_NOT_MOUNTED'
BUDGET = 'NOT_SELECTED_FOR_BOUNDED_VIDEO_SAMPLING'


def _finite(value: Any, *, minimum: float | None = None,
            maximum: float | None = None) -> bool:
    if type(value) not in (float, int) or not math.isfinite(value):
        return False
    if minimum is not None and value < minimum:
        return False
    if maximum is not None and value > maximum:
        return False
    return True


def _source_hash(r: dict, s: dict) -> str:
    return hashlib.sha256((json.dumps(r, sort_keys=True) + '\n' +
                           json.dumps(s, sort_keys=True)).encode()).hexdigest()


def audit_video_report(report: dict, r: dict, s: dict) -> dict:
    require(isinstance(report, dict), 'Report must be a JSON object')
    parsed = parse_reports(r, s)
    expected = build_report(r, s)
    require(report.get('status') == expected['status'], 'Wrong research report status')
    for key in ('production_qualified', 'independent_camera_authentication',
                'false_alarm_rate_known', 'incident_recovery_authorized'):
        require(report.get(key) is False, 'Unsafe claim in video report: ' + key)
    require(report.get('source_evidence_sha256') == _source_hash(r, s),
            'Phase3R/S source evidence checksum mismatch')
    require(report.get('source_pins') == parsed['source_pins'],
            'Pinned video/annotation/reference identity mismatch')
    require(report.get('sampling_audit') == parsed['audit'],
            'Selection audit disagrees with original numeric evidence')
    require(report.get('number_of_windows') == len(parsed['windows']) and
            report.get('selected_normal_labeled_hours') == len(parsed['windows'])*180/3600,
            'Selected control denominator mismatch')
    require(report.get('by_day') == expected['by_day'],
            'Per-day candidate accounting differs from original reports')
    rows = report.get('priority_queue')
    require(isinstance(rows, list) and len(rows) == len(parsed['windows']),
            'Video report contains missing or duplicate control windows')
    source_windows = {w['id']: w for w in parsed['windows']}
    identifiers = [item.get('id') for item in rows if isinstance(item, dict)]
    require(len(identifiers) == len(set(identifiers)),
            'Video report contains duplicated control IDs')
    seen = set()
    groups = {}
    for day in DAYS:
        groups[day] = {'selected_windows': 0, 'measured_video_windows': 0,
                       'not_measured_windows': 0, 'sampled_video_frames': 0,
                       'candidate_bearing_measured_windows': 0,
                       'candidate_bearing_unmeasured_windows': 0,
                       'sparse_sharpness_change_possible_candidate_windows': 0,
                       'sparse_sharpness_change_possible_comparator_windows': 0,
                       'geometric_proxy_unavailable_measured_windows': 0}
    for item in rows:
        require(isinstance(item, dict), 'Malformed priority_queue window')
        key = item.get('id')
        require(key in source_windows and key not in seen,
                'Unknown or duplicated selected control frame range')
        seen.add(key)
        source = source_windows[key]
        for identity in ('day', 'start_frame', 'end_frame', 'source_phase',
                         'selection', 'stratum', 'policies', 'sampled_seconds',
                         'paired_observations', 'unknown_observations',
                         'illumination_confounded_samples'):
            require(item.get(identity) == source[identity],
                    f'Window identity/score corrupted at {key}: {identity}')
        require(item.get('physical_condition_verified') is False and
                item.get('independent_ground_truth') is False,
                'Numeric windows are not independently visually adjudicated')
        video = item.get('local_video_evidence')
        require(isinstance(video, dict) and
                video.get('status') in SUPPORTED_VIDEO_STATUSES,
                f'Unsupported video observation status: {key}')
        require(video.get('physical_camera_health_verified') is False and
                video.get('has_independent_visual_truth') is False,
                'Video feature evidence cannot certify camera health')
        g = groups[item['day']]
        g['selected_windows'] += 1
        candidate = item['policies']['sharpness_3_consecutive']['window_with_candidate']
        if video['status'] != MEASURED:
            g['not_measured_windows'] += 1
            g['candidate_bearing_unmeasured_windows'] += int(candidate)
            continue
        require(video.get('video_or_frames_exported') is False and
                video.get('camera_tamper_event_proven') is False and
                video.get('approved_camera_reference_used') is False and
                video.get('scene_incident_or_recovery_changed') is False and
                video.get('feature_cutoff_not_production_approved') is True and
                video.get('scene_geometry_proxy_not_camera_displacement_truth') is True,
                'Local video feature production/independent-truth claim is invalid')
        count = video.get('sampled_source_frames')
        require(type(count) is int and 4 <= count <= 48 and
                video.get('first_sample_frame') == item['start_frame'] and
                video.get('last_sample_frame') == item['end_frame'],
                f'Local video frame count or bounds mismatch at {key}')
        for metric in ('first_frame_laplacian_variance',
                       'last_frame_laplacian_variance',
                       'min_laplacian_ratio_to_first_window_frame'):
            require(_finite(video.get(metric), minimum=0),
                    f'Invalid sparse sharpness statistic: {key} {metric}')
        require(video['min_laplacian_ratio_to_first_window_frame'] <= 1.00001,
                'Minimum ratio cannot exceed first window sample baseline')
        for metric in ('max_luma_delta_between_sparse_samples', 'mean_luma_range'):
            require(_finite(video.get(metric), minimum=0, maximum=255),
                    f'Invalid luma statistic: {key} {metric}')
        supported = video.get('geometric_proxy_supported_comparisons')
        unknown = video.get('geometric_proxy_unknown_comparisons')
        require(type(supported) is int and type(unknown) is int and
                0 <= supported <= count-1 and supported+unknown == count-1,
                'Unknown geometry must be counted, not treated as stationary')
        displacement = video.get('max_normalized_center_displacement_proxy')
        require((displacement is None and supported == 0) or
                (displacement is not None and supported > 0 and
                 _finite(displacement, minimum=0)),
                'Geometry displacement statistic disagrees with evidence availability')
        assessment = video.get('derived_sparse_feature_assessment')
        require(assessment == (
            'SUBSTANTIAL_SPARSE_SHARPNESS_CHANGE_POSSIBLE'
            if video['min_laplacian_ratio_to_first_window_frame'] < .5 else
            'NO_LARGE_SPARSE_SHARPNESS_CHANGE_OBSERVED'),
            'Invalid sparse feature categorization')
        g['measured_video_windows'] += 1
        g['sampled_video_frames'] += count
        g['candidate_bearing_measured_windows'] += int(candidate)
        g['geometric_proxy_unavailable_measured_windows'] += int(supported == 0)
        if assessment == 'SUBSTANTIAL_SPARSE_SHARPNESS_CHANGE_POSSIBLE':
            which = ('sparse_sharpness_change_possible_candidate_windows' if candidate else
                     'sparse_sharpness_change_possible_comparator_windows')
            g[which] += 1
    require(seen == set(source_windows), 'The video evidence does not cover original window IDs')
    measured_total = sum(g['measured_video_windows'] for g in groups.values())
    flag = report.get('recordings_available_in_workspace')
    require(type(flag) is bool and flag is (measured_total > 0),
            'Video mounted status contradicts measured evidence')
    legacy_skipped = sum(1 for row in rows
                         if row['local_video_evidence']['status'] == MISSING) if measured_total else 0
    return {
        'status': 'PHASE3V_IMPORTED_VIDEO_FEATURE_EVIDENCE_AUDITED_RESEARCH_ONLY',
        'source_evidence_sha256': report['source_evidence_sha256'],
        'source_video_hash_verification_declared_by_original_local_run': measured_total > 0,
        'actual_source_video_sha256_recomputed_in_this_audit': False,
        'actual_videos_reopened_in_this_audit': False,
        'selected_windows': len(rows),
        'measured_video_windows': measured_total,
        'unmeasured_video_windows': len(rows)-measured_total,
        'measured_video_frames': sum(g['sampled_video_frames'] for g in groups.values()),
        'per_day': groups,
        'legacy_unmeasured_windows_labeled_source_not_mounted_despite_video_present': legacy_skipped,
        'coverage_complete_on_preselected_windows': measured_total == len(rows),
        'numeric_model_candidate_is_independently_verified_tampering': False,
        'field_false_alert_rate_established': False,
        'approved_physical_camera_reference_available': False,
        'production_qualified': False,
        'diagnostic_notes': [
            'VIDEO-MEASURED indicates scalar features of decoded AVI frames, not physical ground truth',
            'Sparse 12-frame features are NOT temporally aligned to all 2-second policy samples',
            'Geometry comparison unknown is not proof of camera immobility or healthy view',
            'Earlier SOURCE_VIDEO_NOT_MOUNTED on unmeasured windows reflects bounded selection budget',
            'Selected normal-annotated controls are not an unbiased or held-out sample',
            'No alert suppression, incident closure, reference reset or operational release is authorized',
        ],
    }
