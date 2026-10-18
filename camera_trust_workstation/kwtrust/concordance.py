"""Phase 3W: frozen development-sample scalar signal concordance.

Not a physical camera-state classifier, benchmark, false alarm estimator,
threshold optimizer, or source of camera-health labels. The two signals
have DISTINCT sampling cadences and reference procedures. Exploratory 0.5
is an existing research descriptor and MUST NOT be tuned here.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any

from .analysis import EvidenceError, require
from .audit import audit_video_report, MEASURED

VERSION = 'PHASE3W_FULL_SELECTED_WINDOW_SIGNAL_CONCORDANCE_RESEARCH_ONLY'
REF_POLICY = 'sharpness_3_consecutive'
PROXY_CUTOFF = 0.5
STATES = ('CANDIDATE_AND_SPARSE_CHANGE',
          'CANDIDATE_WITHOUT_SPARSE_CHANGE',
          'NONCANDIDATE_WITH_SPARSE_CHANGE',
          'NEITHER_RESEARCH_CUE')


def _measure(record: dict) -> dict:
    video = record['local_video_evidence']
    candidate = record['policies'][REF_POLICY]['window_with_candidate']
    sharp = video['min_laplacian_ratio_to_first_window_frame']
    sparse = sharp < PROXY_CUTOFF
    state = (STATES[0] if candidate and sparse else
             STATES[1] if candidate else
             STATES[2] if sparse else STATES[3])
    supported = video['geometric_proxy_supported_comparisons']
    return {
        'id': record['id'], 'day': record['day'],
        'start_frame': record['start_frame'], 'end_frame': record['end_frame'],
        'comparison_group': state, 'numerical_candidate': candidate,
        'candidate_episode_starts': record['policies'][REF_POLICY]['episodes'],
        'sparse_sharpness_change_proxy': sparse,
        'sparse_min_laplacian_ratio': sharp,
        'lighting_confounded_paired_samples': record['illumination_confounded_samples'],
        'geometric_proxy_supported_pairs': supported,
        'geometric_proxy_unknown_pairs': video['geometric_proxy_unknown_comparisons'],
        'max_normalized_center_displacement_proxy': video['max_normalized_center_displacement_proxy'],
        'physical_camera_health_known': False,
        'camera_displacement_proven': False,
    }


def diagnose(full_report: dict, r: dict, s: dict, previous_report: dict | None = None) -> dict:
    """Gate on the Phase3R/S audit and require ALL 40 AVI feature windows.

    Optional previous report: ensure reproducibility of the original 20
    window feature dictionaries, and never count missing old cases as healthy.
    """
    verified = audit_video_report(full_report, r, s)
    require(verified['selected_windows'] == 40 and
            verified['coverage_complete_on_preselected_windows'] is True and
            verified['measured_video_windows'] == 40 and
            verified['measured_video_frames'] == 480,
            'Complete frozen 40-window/480-frame AVI feature analysis required')
    require(full_report.get('video_feature_coverage') == {
        'selected_windows': 40,
        'measured_windows': 40,
        'unmeasured_windows': 0,
        'sampled_video_frames': 480,
        'full_selected_window_coverage': True,
        'sampling_is_development_not_physical_truth': True,
    }, 'Published feature coverage contradicts source window audit')

    measured = sorted([_measure(row) for row in full_report['priority_queue']],
                      key=lambda x: (x['day'], x['start_frame']))
    previous_integrity = {'provided': previous_report is not None,
                          'prior_measured_windows': 0,
                          'previous_scalar_evidence_reproduced': None}
    if previous_report is not None:
        prior = audit_video_report(previous_report, r, s)
        require(prior['measured_video_windows'] == 20 and
                prior['unmeasured_video_windows'] == 20,
                'Expected older bounded 20-window AVI source report')
        existing = {w['id']: w['local_video_evidence'] for w in previous_report['priority_queue']
                    if w['local_video_evidence']['status'] == MEASURED}
        fresh = {w['id']: w['local_video_evidence'] for w in full_report['priority_queue']}
        require(len(existing) == 20 and all(fresh.get(k) == v for k,v in existing.items()),
                'Previously sampled AVI scalar measurements were not exactly reproduced')
        previous_integrity.update({'prior_measured_windows': len(existing),
                                   'previous_scalar_evidence_reproduced': True,
                                   'prior_unmeasured_windows_now_sampled': 20})

    by_day = {}
    for day in ('day3','day4'):
        selected = [row for row in measured if row['day']==day]
        ct = Counter(row['comparison_group'] for row in selected)
        by_day[day] = {
            'preselected_normal_labeled_windows': len(selected),
            'candidate_and_sparse_change': ct[STATES[0]],
            'candidate_without_sparse_change': ct[STATES[1]],
            'noncandidate_with_sparse_change': ct[STATES[2]],
            'neither_research_cue': ct[STATES[3]],
            'geometric_proxy_supported_windows': sum(x['geometric_proxy_supported_pairs']>0 for x in selected),
            'geometric_proxy_unknown_windows': sum(x['geometric_proxy_supported_pairs']==0 for x in selected),
            'geometric_proxy_supported_pairs': sum(x['geometric_proxy_supported_pairs'] for x in selected),
            'geometric_proxy_unknown_pairs': sum(x['geometric_proxy_unknown_pairs'] for x in selected),
            'illumination_confound_present_windows': sum(x['lighting_confounded_paired_samples']>0 for x in selected),
        }
        require(len(selected)==20, 'Expected 20 controls for each source day')
        require(sum(ct.values()) == 20, 'Each selected window must occupy exactly one comparison group')
    overall_ct = Counter(item['comparison_group'] for item in measured)
    require(sum(overall_ct.values()) == 40, 'Classification of existing research cues must be exhaustive')
    focus = sorted((row for row in measured if row['comparison_group'] != STATES[3]),
                   key=lambda x:(STATES.index(x['comparison_group']),x['day'],x['start_frame']))
    largest_geometry_proxies = sorted(
        [row for row in measured if row['geometric_proxy_supported_pairs']>0],
        key=lambda x:(-x['max_normalized_center_displacement_proxy'],x['day'],x['start_frame'])
    )[:5]
    return {
        'status': VERSION,
        'input_phase3r_s_checksum': full_report['source_evidence_sha256'],
        'full_report_sha256': hashlib.sha256(json.dumps(full_report,sort_keys=True).encode()).hexdigest(),
        'previous_report_integrity': previous_integrity,
        'window_count': 40,
        'selected_exposure_hours': 2.0,
        'sampled_source_frames': 480,
        'sparse_cutoff_existing_exploratory_value_not_fitted': PROXY_CUTOFF,
        'temporal_sampling_comparable': False,
        'policy_selected_for_production': False,
        'source_is_held_out': False,
        'physical_ground_truth_available': False,
        'event_false_alarm_rate_established': False,
        'camera_movement_truth_inferred_from_geometry': False,
        'scene_incident_or_reference_mutation_authorized': False,
        'video_or_frames_exported': False,
        'overall_concordance': {state: overall_ct[state] for state in STATES},
        'by_day': by_day,
        'windows_for_independent_followup': focus,
        'largest_geometric_proxies_not_displacement_proof': largest_geometry_proxies,
        'geometric_coverage': {
            'supported_windows': sum(v['geometric_proxy_supported_windows'] for v in by_day.values()),
            'unknown_windows': sum(v['geometric_proxy_unknown_windows'] for v in by_day.values()),
            'supported_sparse_pair_comparisons': sum(v['geometric_proxy_supported_pairs'] for v in by_day.values()),
            'unknown_sparse_pair_comparisons': sum(v['geometric_proxy_unknown_pairs'] for v in by_day.values()),
        },
        'interpretation': [
            'Two frozen development cues have different temporal sampling; disagreement is diagnostic, not classification error.',
            '0.5 is previously inspected exploratory sparse ratio, not a new validated threshold.',
            'All 40 selected normal-labeled windows now have scalar video features, not independently authenticated camera health.',
            'Unknown geometric comparisons are not evidence of unchanged camera pose.',
            'Large geometric proxy values may be tracking or low-texture artifacts and are not camera displacement truth.',
            'No operational warning policy, incident workflow, physical reference or recovery action changed.',
            'Independent custody-controlled held-out tests remain required before field performance claims.',
        ]
    }
