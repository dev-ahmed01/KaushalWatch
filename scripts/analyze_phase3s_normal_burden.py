#!/usr/bin/env python3
"""Phase 3S: non-operational numeric audit of Phase 3R normal-window burden.

Selection, comparison cutoffs and exposure are development-only and
previously inspected. Output is a summary and numeric frame-range triage
manifest, NOT false-alarm adjudication, a trained threshold or image media.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path

INPUT_STATUS = "PHASE3R_TWO_DAY_SYSTEMATIC_NORMAL_RESEARCH_ONLY"
DAY_STATUS = "PHASE3R_SYSTEMATIC_NORMAL_RESEARCH_NOT_HELD_OUT"
POLICIES = (
    "phase3p_original_unmodified", "sharpness_only_numeric",
    "sharpness_2_of_previous_3", "sharpness_3_consecutive",
)


def demand(condition: bool, error: str) -> None:
    if not condition:
        raise ValueError(error)


def nonnegative(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def audit_day(name: str, day: dict) -> dict:
    demand(isinstance(day, dict) and day.get("status") == DAY_STATUS, "Unexpected research day status")
    for key in (
        "production_qualified", "source_is_held_out",
        "normal_annotation_is_independent_health_truth",
        "source_reference_is_physical_camera_approved",
        "scene_raw_review_status_measured",
        "spatial_evidence_status_measured",
        "full_day_detector_replayed", "images_or_video_exported",
        "operational_incident_or_reference_mutated",
    ):
        demand(day.get(key) is False, "Research-only gate mismatch " + key)
    sample_seconds = day.get("sample_rate_seconds")
    demand(nonnegative(sample_seconds) and sample_seconds > 0, "Invalid cadence")
    audit = day.get("sampling_audit")
    windows = day.get("windows")
    demand(isinstance(audit, dict) and isinstance(windows, list),
           "Missing sampling manifest or window data")
    demand(day.get("selected_window_count") == audit.get("selected_windows") == len(windows),
           "Selected window denominator mismatch")
    demand(audit.get("no_random_or_unbiased_sampling_claim") is True,
           "Nonrepresentative selection must be declared")
    demand(audit.get("normal_labeled_not_authenticated_camera_healthy") is True,
           "Normal annotation must not be equated with camera health")
    selected_strata = sum(w.get("selection") == "fixed_progress_strata" for w in windows)
    selected_post = sum(w.get("control_stratum", "").startswith("after_event_") for w in windows)
    selected_pre = sum(w.get("control_stratum", "").startswith("before_event_") for w in windows)
    demand(selected_strata == audit.get("selected_time_strata"),
           "Stratum audit count differs from selected windows")
    adj = audit.get("event_adjacency", {})
    demand(isinstance(adj, dict) and
           selected_pre == adj.get("before", {}).get("selected_nonoverlapping") and
           selected_post == adj.get("after", {}).get("selected_nonoverlapping"),
           "Event adjacency audit disagrees with source window list")
    demand(day.get("sampled_numeric_positions") ==
           sum(w.get("sampled_positions", -1) for w in windows),
           "Total samples mismatch")
    demand(nonnegative(day.get("approx_annotated_normal_sample_hours")) and
           abs(day["approx_annotated_normal_sample_hours"] -
               sum(w["sampled_positions"] for w in windows) * sample_seconds / 3600) < 0.00001,
           "Numeric exposure mismatch")
    policies = day.get("policies")
    demand(isinstance(policies, dict) and set(policies) == set(POLICIES),
           "Source policy contract mismatch")
    for a, first in enumerate(windows):
        demand(first.get("camera_image_healthy_verified") is False and
               first.get("media_exported") is False and
               first.get("production_action_authorized") is False,
               "Control window makes unauthorized health/release claim")
        demand(type(first.get("start_frame")) is int and
               type(first.get("end_frame")) is int and
               1 <= first["start_frame"] <= first["end_frame"],
               "Invalid video frame range")
        for second in windows[a+1:]:
            demand(first["end_frame"] < second["start_frame"] or
                   second["end_frame"] < first["start_frame"],
                   "Duplicate or overlapping numeric exposure")
        demand(isinstance(first.get("policies"), dict) and
               set(first["policies"]) == set(POLICIES),
               "Incomplete per-window policy reporting")
        states = first.get("comparison_states")
        demand(isinstance(states, dict) and
               all(type(v) is int and v >= 0 for v in states.values()) and
               sum(states.values()) == first.get("sampled_positions"),
               "Comparison-state accounting mismatch")
        demand(all(v in (
            "INSUFFICIENT_PAST_SAMPLE_COVERAGE",
            "NONINFORMATIVE_PAST_DENOMINATOR_ABSTAIN",
            "PAIRED_UNVERIFIED_NUMERIC_OBSERVATION",
            "UNKNOWN_LOW_TEXTURE_ABSTAIN",
            "REFERENCE_TEXTURE_INSUFFICIENT_ABSTAIN",
            "DISCONTINUOUS_HISTORY",
        ) for v in states), "Unexpected evidence state")
        for policy in POLICIES:
            score = first["policies"][policy]
            demand(score.get("not_verified_false_alerts") is True and
                   score.get("no_incident_created_or_closed") is True,
                   "Candidates cannot be promoted to incident/false alarm")
            demand(all(type(score.get(k)) is int and score[k] >= 0
                       for k in ("candidate_episode_starts", "candidate_active_samples",
                                 "longest_candidate_contiguous_samples")),
                   "Invalid numeric candidate counts")
            demand(score["candidate_active_samples"] <= first["sampled_positions"] and
                   score["candidate_episode_starts"] <= score["candidate_active_samples"],
                   "Candidate episodes exceed observed samples")
            demand(score.get("candidate_window_has_any_flag") is
                   (score["candidate_active_samples"] > 0),
                   "Candidate-bearing window flag disagrees with active sample count")
    manifest = []
    aggregate = {}
    for policy in POLICIES:
        episode_count = sum(w["policies"][policy]["candidate_episode_starts"] for w in windows)
        sample_count = sum(w["policies"][policy]["candidate_active_samples"] for w in windows)
        any_count = sum(w["policies"][policy]["candidate_window_has_any_flag"] for w in windows)
        stored = policies[policy]
        demand(stored.get("candidate_episode_starts_on_annotated_normal") == episode_count and
               stored.get("candidate_active_samples_on_annotated_normal") == sample_count and
               stored.get("control_windows_with_any_candidate") == any_count and
               stored.get("candidate_burden_is_conditional_on_selected_controls_only") is True,
               "Summary candidate counts differ from per-window evidence")
        aggregate[policy] = {
            "selected_normal_control_windows_with_candidates": any_count,
            "candidate_episode_starts": episode_count,
            "candidate_active_samples": sample_count,
            "approx_candidate_active_seconds": round(sample_count * sample_seconds, 3),
            "per_selected_exposure_hour_descriptive_count_only": round(
                episode_count / day["approx_annotated_normal_sample_hours"], 4
            ) if day["approx_annotated_normal_sample_hours"] > 0 else None,
            "cannot_infer_false_alert_rate": True,
        }
    for w in windows:
        p = w["policies"]["sharpness_3_consecutive"]
        if not p["candidate_window_has_any_flag"]:
            continue
        total = w["sampled_positions"]
        illumination = w.get("confounds", {}).get("ILLUMINATION_UNRESOLVED", 0)
        manifest.append({
            "day": name, "stratum": w["control_stratum"],
            "selection": w["selection"],
            "start_frame": w["start_frame"], "end_frame": w["end_frame"],
            "research_only_3_consecutive_candidate_episodes": p["candidate_episode_starts"],
            "research_only_3_consecutive_active_samples": p["candidate_active_samples"],
            "illumination_confounded_paired_samples": illumination,
            "paired_samples_with_unknown_raw_scene_status":
                w.get("confounds", {}).get("RAW_SCENE_CUE_NOT_MEASURED", 0),
            "sampled_positions": total,
            "triage_requires_independent_visual_verification": True,
            "private_media_exported": False,
            "not_an_adjudicated_false_alert": True,
        })
    manifest.sort(key=lambda x: (
        -x["research_only_3_consecutive_candidate_episodes"],
        -x["research_only_3_consecutive_active_samples"],
        x["start_frame"],
    ))
    return {
        "day": name,
        "selected_windows": len(windows),
        "normal_labeled_exposure_hours": day["approx_annotated_normal_sample_hours"],
        "sampling_audit": {
            "time_strata_selected": selected_strata,
            "pre_event_selected": selected_pre,
            "post_event_selected": selected_post,
            "pre_event_predeclared_skipped_overlap":
                adj["before"].get("rejected_overlap"),
            "post_event_predeclared_skipped_overlap":
                adj["after"].get("rejected_overlap"),
            "unfilled_time_strata": audit.get("unfilled_time_strata"),
        },
        "policies": aggregate,
        "candidate_window_triage": manifest,
        "normal_label_is_healthy_camera_verification": False,
        "false_alert_rate_established": False,
    }


def analyze(report: dict) -> dict:
    demand(isinstance(report, dict) and report.get("status") == INPUT_STATUS,
           "Require complete 3R two-day research report")
    for key in (
        "automatic_reference_reenrollment_or_recovery",
        "held_out_validation", "media_exported",
        "operational_scene_warnings_modified", "production_qualified",
        "false_alert_rate_established",
    ):
        demand(report.get(key) is False, "Top-level release gate mismatch " + key)
    demand(report.get("development_reused") is True, "Original research reuse not declared")
    days = report.get("days")
    demand(isinstance(days, dict) and set(days) == {"day3", "day4"},
           "Two complete research days required")
    by_day = {day: audit_day(day, days[day]) for day in ("day3", "day4")}
    totals = {}
    for policy in POLICIES:
        totals[policy] = {
            "selected_window_candidate_episode_starts": sum(
                x["policies"][policy]["candidate_episode_starts"]
                for x in by_day.values()),
            "selected_window_active_samples": sum(
                x["policies"][policy]["candidate_active_samples"]
                for x in by_day.values()),
            "windows_with_any_candidate": sum(
                x["policies"][policy]["selected_normal_control_windows_with_candidates"]
                for x in by_day.values()),
        }
    return {
        "status": "PHASE3S_NUMERIC_BURDEN_TRIAGE_ONLY",
        "source_status": INPUT_STATUS,
        "development_data_only": True,
        "production_qualified": False,
        "independent_camera_health_review_completed": False,
        "full_day_false_alert_rate_established": False,
        "source_raw_scene_cues_known": False,
        "camera_reference_approved": False,
        "source_media_modified_or_exported": False,
        "operator_incidents_changed": False,
        "sampling_repaired_by_this_numeric_analysis": False,
        "days": by_day,
        "totals": totals,
        "interpretation": [
            "These are numerical candidate counts from selected normal-annotated intervals, not confirmed false alerts",
            "Per selected exposure hour is only a within-sample descriptive ratio; extrapolation to full days forbidden",
            "Day 3 and Day 4 are the same previously investigated development sources",
            "The 3-consecutive condition does not eliminate normal-labelled warnings",
            "Selected pre-event control coverage is missing and must be repaired by label-only selection",
            "Independent review of private source frames needed for nuisance-event root causes",
            "No quality cutoff or scene warning suppression selected or modified",
        ],
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    if a.out.suffix.lower() != ".json" or a.out.exists() or a.input.resolve() == a.out.resolve():
        p.error("Output must be a new unused JSON file and cannot overwrite input")
    report = json.loads(a.input.read_text(encoding="utf-8"))
    result = analyze(report)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with a.out.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({
        "status": result["status"],
        "totals": result["totals"],
        "triage_windows_by_day": {
            name: len(info["candidate_window_triage"])
            for name, info in result["days"].items()
        },
        "output": str(a.out),
        "production_qualified": False,
    }, indent=2))


if __name__ == "__main__":
    main()
