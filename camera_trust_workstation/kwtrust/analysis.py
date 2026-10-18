"""Audited numeric reconstruction of the Phase3R/S development evidence.

The module NEVER declares review truth or false-alarm rates. Candidate episode
counts are observations in intentionally selected normal-annotated windows.
"""
from __future__ import annotations
from collections import Counter
import hashlib
import json
from pathlib import Path

R_STATUS = "PHASE3R_TWO_DAY_SYSTEMATIC_NORMAL_RESEARCH_ONLY"
S_STATUS = "PHASE3S_TWO_DAY_BALANCED_NORMAL_PRE_EVENT_RESEARCH_ONLY"
POLICIES = (
    "phase3p_original_unmodified", "sharpness_only_numeric",
    "sharpness_2_of_previous_3", "sharpness_3_consecutive",
)
DAYS = ("day3", "day4")

class EvidenceError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise EvidenceError(message)


def load_json(path: Path) -> dict:
    if not Path(path).is_file():
        raise EvidenceError(f"Report does not exist: {path}")
    # Numeric reports only; hard cap protects accidental video loading / DoS.
    require(Path(path).stat().st_size <= 20_000_000,
            "Report exceeds 20 MB evidence limit")
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise EvidenceError(f"Malformed source JSON: {path}") from exc
    require(isinstance(data, dict), "Report JSON must be an object")
    return data


def parse_reports(r: dict, s: dict) -> dict:
    require(r.get("status") == R_STATUS and s.get("status") == S_STATUS,
            "Wrong research report versions")
    for field in (
        "production_qualified", "held_out_validation", "false_alert_rate_established",
        "media_exported", "operational_scene_warnings_modified",
        "automatic_reference_reenrollment_or_recovery",
    ):
        require(r.get(field) is False, "Unsafe Phase3R flag: " + field)
    for field in (
        "production_qualified", "media_exported", "operational_scene_cues_modified",
        "camera_physical_reference_approved", "incident_recovery_or_reference_rotation",
    ):
        require(s.get(field) is False, "Unsafe Phase3S flag: " + field)
    require(r.get("development_reused") is True and
            s.get("development_evidence_not_held_out") is True and
            s.get("prior_phase3r_evidence_reused_without_duplicate_window_evaluation") is True,
            "Development/continuity evidence guards missing")
    require(set(r.get("days", {})) == set(DAYS) and
            set(s.get("days", {})) == set(DAYS), "Expected Day 3 and Day 4")

    windows = []
    audit = {}
    source_pins = {}
    for day in DAYS:
        rr = r["days"][day]
        ss = s["days"][day]
        require(rr.get("production_qualified") is False and
                rr.get("normal_annotation_is_independent_health_truth") is False and
                rr.get("source_reference_is_physical_camera_approved") is False and
                rr.get("scene_raw_review_status_measured") is False and
                rr.get("spatial_evidence_status_measured") is False and
                ss.get("physical_camera_reference_approved") is False and
                ss.get("raw_scene_cues_or_spatial_evidence_measured") is False,
                f"Unsafe per-day evidence claims: {day}")
        require(rr.get("sample_rate_seconds") == 2.0,
                "Unexpected Phase3R sampling rate")
        for key in ("source_video_sha256", "source_annotations_sha256"):
            pin = rr.get(key)
            require(isinstance(pin, str) and len(pin) == 64 and
                    all(c in '0123456789abcdef' for c in pin) and pin == ss.get(key),
                    f"Source identity mismatch: {day} {key}")
        source_pins[day] = {
            "video_sha256": rr["source_video_sha256"],
            "annotations_sha256": rr["source_annotations_sha256"],
            "unapproved_development_reference_sha256": rr.get(
                "frozen_unapproved_reference_pixel_sha256"),
        }
        first = rr.get("windows")
        new = ss.get("new_pre_event_numeric_windows")
        require(isinstance(first, list) and len(first) == 16 and
                isinstance(new, list) and len(new) <= 4 and
                ss.get("prior_phase3r_selected_windows") == len(first) and
                ss.get("prior_phase3r_original_numeric_windows_rereplayed") is False and
                ss.get("new_pre_event_windows") == len(new),
                f"Unexpected source window counts: {day}")
        audit[day] = {
            "original_normal_windows": len(first),
            "additional_pre_event_windows": len(new),
            "selected_time_strata": rr.get("sampling_audit", {}).get("selected_time_strata"),
            "selected_post_event_windows": rr.get("sampling_audit", {}).get(
                "event_adjacency", {}).get("after", {}).get("selected_nonoverlapping"),
            "unfilled_pre_event_targets": ss.get("sampling_audit", {}).get(
                "unfilled_pre_event_targets"),
        }
        day_windows = []
        for phase, group in (("phase3r", first), ("phase3s", new)):
            for raw in group:
                start, end = raw.get("start_frame"), raw.get("end_frame")
                require(type(start) is int and type(end) is int and
                        1 <= start <= end, "Invalid window frames")
                require(raw.get("camera_image_healthy_verified") is False and
                        raw.get("production_action_authorized") is False and
                        raw.get("media_exported") is False,
                        "Invalid production/health claim in a window")
                require(raw.get("sampled_positions") == 90 and
                        raw.get("approx_sampled_time_seconds") == 180.0,
                        "Unexpected numeric observation exposure")
                comparison_states = raw.get("comparison_states", {})
                require(isinstance(comparison_states, dict) and
                        all(type(v) is int and v >= 0 for v in comparison_states.values()) and
                        sum(comparison_states.values()) == 90,
                        "Invalid sample denominator or comparison state")
                confounds = raw.get("confounds")
                require(isinstance(confounds, dict) and
                        confounds.get("RAW_SCENE_CUE_NOT_MEASURED", 0) > 0 and
                        confounds.get("SPATIAL_EVIDENCE_NOT_MEASURED", 0) > 0,
                        "Missing unknown raw scene / spatial evidence")
                policy_values = raw.get("policies")
                require(isinstance(policy_values, dict) and
                        set(policy_values) == set(POLICIES),
                        "Invalid policy coverage")
                policies = {}
                for name in POLICIES:
                    score = policy_values[name]
                    episode, active = (score.get("candidate_episode_starts"),
                                       score.get("candidate_active_samples"))
                    require(type(episode) is int and type(active) is int and
                            0 <= episode <= active <= 90 and
                            score.get("candidate_window_has_any_flag") is (active > 0) and
                            score.get("not_verified_false_alerts") is True and
                            score.get("no_incident_created_or_closed") is True,
                            "Invalid candidate episode counts or provenance")
                    policies[name] = {"episodes": episode, "active_samples": active,
                                      "window_with_candidate": active > 0}
                day_windows.append({
                    "id": f"{day}-{start}-{end}", "day": day,
                    "source_phase": phase, "stratum": raw.get("control_stratum", ""),
                    "selection": raw.get("selection", ""),
                    "start_frame": start, "end_frame": end,
                    "sampled_seconds": 180.0,
                    "paired_observations": comparison_states.get(
                        "PAIRED_UNVERIFIED_NUMERIC_OBSERVATION", 0),
                    "unknown_observations": 90 - comparison_states.get(
                        "PAIRED_UNVERIFIED_NUMERIC_OBSERVATION", 0),
                    "illumination_confounded_samples": confounds.get(
                        "ILLUMINATION_UNRESOLVED", 0),
                    "quality_hypotheses": raw.get("quality_hypotheses", {}),
                    "policies": policies,
                    "physical_condition_verified": False,
                    "independent_ground_truth": False,
                })
        sorted_windows = sorted(day_windows, key=lambda x: x["start_frame"])
        for previous, current in zip(sorted_windows, sorted_windows[1:]):
            require(previous["end_frame"] < current["start_frame"],
                    f"Overlapping windows found for {day}")
        for policy in POLICIES:
            counted_r = sum(w["policies"][policy]["episodes"]
                            for w in day_windows if w["source_phase"] == "phase3r")
            counted_s = sum(w["policies"][policy]["episodes"]
                            for w in day_windows if w["source_phase"] == "phase3s")
            summary = ss["policy_comparison"][policy]
            require(counted_r == summary.get("existing_normal_labeled_candidate_episode_starts") and
                    counted_s == summary.get("new_pre_event_normal_labeled_candidate_episode_starts") and
                    counted_r + counted_s == summary.get(
                        "combined_development_sample_candidate_episode_starts"),
                    "Source episode totals disagree with individual windows")
        windows.extend(day_windows)
    return {"windows": windows, "source_pins": source_pins, "audit": audit}


def build_report(r: dict, s: dict, *, video: dict | None = None, causal: dict | None = None) -> dict:
    parsed = parse_reports(r, s)
    windows = parsed["windows"]
    video = video or {}
    expected_ids = {w["id"] for w in windows}
    require(set(video) <= expected_ids, "Unexpected video feature window identifier")
    require(all(isinstance(v, dict) and v.get("status") ==
                "UNVERIFIED_LOCAL_VIDEO_FEATURES_NOT_GROUND_TRUTH" and
                v.get("physical_camera_health_verified") is False and
                v.get("video_or_frames_exported") is False for v in video.values()),
            "Invalid injected video analysis claims")
    priority = []
    for win in windows:
        item = dict(win)
        # Sorting uses exploratory signals only, never claims reviewed truth.
        signal = win["policies"]["sharpness_3_consecutive"]
        item["diagnostic_priority"] = (
            2 if signal["window_with_candidate"] else 1
        )
        item["priority_reason"] = (
            "Unreviewed persistent numeric sharpness candidate"
            if signal["window_with_candidate"] else
            "Comparative normal-labeled control; no persistent numeric candidate"
        )
        item["local_video_evidence"] = video.get(win["id"], {
            "status": ("NOT_SELECTED_FOR_BOUNDED_VIDEO_SAMPLING" if video else
                       "SOURCE_VIDEO_NOT_MOUNTED"),
            "physical_camera_health_verified": False,
            "has_independent_visual_truth": False,
        })
        priority.append(item)
    priority.sort(key=lambda x: (-x["diagnostic_priority"],
                                -x["policies"]["sharpness_3_consecutive"]["episodes"],
                                x["day"], x["start_frame"]))
    by_day = {}
    for day in DAYS:
        selected = [x for x in windows if x["day"] == day]
        by_day[day] = {
            "window_count": len(selected),
            "selected_normal_labeled_hours": len(selected) * 180 / 3600,
            "policy_candidates": {
                name: {
                    "candidate_episode_starts": sum(
                        x["policies"][name]["episodes"] for x in selected),
                    "windows_with_numeric_candidate": sum(
                        x["policies"][name]["window_with_candidate"] for x in selected),
                    "candidate_active_samples": sum(
                        x["policies"][name]["active_samples"] for x in selected),
                    "verified_false_alarms": None,
                } for name in POLICIES
            },
        }
    raw_hash = hashlib.sha256((json.dumps(r, sort_keys=True) + "\n" +
                               json.dumps(s, sort_keys=True)).encode()).hexdigest()
    causal_evidence = (analyze_causal_development(causal, parsed["source_pins"])
                       if causal is not None else None)
    return {
        "status": "OFFLINE_DEVELOPMENT_EVIDENCE_ANALYZED_NO_PHYSICAL_TRUTH",
        "annotated_event_window_evidence": causal_evidence,
        "dataset": "Phase3R/S selected normal-annotated controls",
        "source_evidence_sha256": raw_hash,
        "source_pins": parsed["source_pins"],
        "sampling_audit": parsed["audit"],
        "number_of_windows": len(windows),
        "selected_normal_labeled_hours": len(windows)*180/3600,
        "by_day": by_day,
        "priority_queue": priority,
        "no_human_review_required_to_run_numeric_analysis": True,
        "production_qualified": False,
        "independent_camera_authentication": False,
        "false_alarm_rate_known": False,
        "incident_recovery_authorized": False,
        "recordings_available_in_workspace": bool(video),
        "video_feature_coverage": {
            "selected_windows": len(windows),
            "measured_windows": len(video),
            "unmeasured_windows": len(windows) - len(video),
            "sampled_video_frames": sum(v.get("sampled_source_frames", 0) for v in video.values()),
            "full_selected_window_coverage": len(video) == len(windows),
            "sampling_is_development_not_physical_truth": True,
        },
        "limitations": [
            "Source windows intentionally sampled; cannot infer field false-alert rate",
            "Existing normal labels do not prove healthy or usable camera images",
            "Previously inspected cutoff and development data are not held-out",
            "Camera physical provenance and fixed reference are unapproved",
            "Raw scene and spatial evidence are UNMEASURED, never healthy by default",
            "Automatic feature observations cannot certify malicious tampering or repair",
            "No production scene cues, incidents, warnings, or thresholds are modified",
        ],
    }


def analyze_causal_development(report: dict, source_pins: dict) -> dict:
    """Additional Phase3P event-window snapshot; never independent performance."""
    require(report.get('status') ==
            'PHASE3P_BOUNDED_TWO_DAY_CAUSAL_NUMERIC_EVIDENCE_ONLY',
            'Unexpected Phase3P event report')
    for key in ('production_qualified', 'all_video_frames_replayed',
                'media_exported', 'operational_alerts_modified',
                'automatic_reference_reset_or_recovery'):
        require(report.get(key) is False, 'Phase3P unsafe source gate '+key)
    require(set(report.get('days', {})) == set(DAYS),
            'Require two Phase3P event days')
    grouped = {}
    for day in DAYS:
        source = report['days'][day]
        require(source.get('status') ==
                'PHASE3P_BOUNDED_CAUSAL_DEVELOPMENT_REPLAY_NOT_HELD_OUT' and
                source.get('reference_is_approved') is False and
                source.get('source_is_held_out') is False and
                source.get('scene_raw_review_status_measured') is False and
                source.get('spatial_evidence_status_measured') is False,
                'Phase3P source has unsafe unmeasured claims')
        require(source.get('source_video_sha256') ==
                source_pins[day]['video_sha256'] and
                source.get('source_annotations_sha256') ==
                source_pins[day]['annotations_sha256'],
                'Phase3P recording identity differs from Phase3R/S')
        grouped[day] = {}
        controls = source.get('windows', [])
        require(isinstance(controls, list), 'Missing Phase3P target windows')
        for kind in ('defocused','moved','normal_control'):
            selected = [w for w in controls if w.get('kind') == kind]
            require(len(selected) == source.get('summary', {}).get(kind, {}).get('selected_windows'),
                    'Phase3P event window counts disagree')
            detected = []
            target_samples = 0
            target_candidate_samples = 0
            for win in selected:
                samples = win.get('samples')
                require(isinstance(samples, list) and samples and
                        win.get('frames_or_media_exported') is False,
                        'Phase3P source samples missing or media exported')
                inside = []
                for sample in samples:
                    if (kind != 'normal_control' and
                        sample.get('annotation_class_for_posthoc_evaluation_only') == kind and
                        isinstance(sample.get('offset_from_target_start_seconds_for_posthoc_analysis'), (int,float)) and
                        sample['offset_from_target_start_seconds_for_posthoc_analysis'] >= 0):
                        inside.append(sample)
                target_samples += len(inside)
                active = [sample for sample in inside if sample.get('exploratory_drop_0_5') is True]
                target_candidate_samples += len(active)
                if kind != 'normal_control':
                    detected.append(bool(active))
            require(target_samples == source['summary'][kind]['annotated_target_samples_in_window'] and
                    target_candidate_samples == source['summary'][kind]['exploratory_drop_samples_inside_target'],
                    'Phase3P source target counts disagree')
            grouped[day][kind] = {
                'selected_windows': len(selected),
                'annotated_target_sample_count': target_samples,
                'candidate_active_inside_annotated_target': target_candidate_samples,
                'windows_with_any_original_candidate_inside_target':
                    sum(detected) if detected else None,
                'source_annotation_not_blinded_physical_truth': True,
                'not_field_recall_or_precision': True,
            }
    return {
        'status': 'PHASE3P_ANNOTATED_DEVELOPMENT_EVENT_WINDOW_CONTEXT_ONLY',
        'days': grouped,
        'known_development_sample_not_independent': True,
        'candidate_does_not_certify_physical_camera_tampering': True,
        'calibrated_latency_established': False,
        'production_qualified': False,
    }
