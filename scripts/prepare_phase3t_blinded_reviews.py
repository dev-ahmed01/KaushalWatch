#!/usr/bin/env python3
"""Phase 3T: blinded, local-only independent visual review case assignments.

Inputs are the existing development-only Phase3R/3S numeric reports. This
module NEVER opens or exports camera footage. It produces two identical
case sets with blind review order, plus a distinct model-evidence key for
later comparison. The reviewer CSVs reveal only video alias/frame range
and physical observation questions, NEVER the model hypothesis/score,
sampling stratum, original annotation or candidate predictions.

Case sampling intentionally enriches candidate windows; do not interpret
reviewed case counts as random/unbiased camera false-alert estimates.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

DAY3 = "day3"
DAY4 = "day4"
DAYS = (DAY3, DAY4)
POLICIES = (
    "phase3p_original_unmodified",
    "sharpness_only_numeric",
    "sharpness_2_of_previous_3",
    "sharpness_3_consecutive",
)
STAGE_R = "PHASE3R_TWO_DAY_SYSTEMATIC_NORMAL_RESEARCH_ONLY"
STAGE_S = "PHASE3S_TWO_DAY_BALANCED_NORMAL_PRE_EVENT_RESEARCH_ONLY"
FIELDS = (
    "case_id", "video_alias", "start_frame", "end_frame",
    "reviewer_id", "footage_available_yes_no_unknown",
    "visible_focus_loss_yes_no_uncertain", "lighting_transition_yes_no_uncertain",
    "physical_camera_displacement_yes_no_uncertain",
    "foreground_occlusion_yes_no_uncertain",
    "image_usable_for_human_observation_yes_no_uncertain",
    "reviewer_confidence_low_medium_high",
    "short_observation_notes_without_person_identifiers",
)
FLAG_VALUES = {"yes", "no", "uncertain"}
FOOTAGE_VALUES = {"yes", "no", "unknown"}
CONFIDENCE_VALUES = {"low", "medium", "high"}


def require(flag: bool, reason: str) -> None:
    if not flag:
        raise ValueError(reason)


def _nonnegative_int(value: Any) -> bool:
    return type(value) is int and value >= 0


def _complete_sources(r: dict, s: dict) -> None:
    require(isinstance(r, dict) and r.get("status") == STAGE_R,
            "Require Phase3R complete numeric source")
    require(isinstance(s, dict) and s.get("status") == STAGE_S,
            "Require Phase3S complete numeric source")
    for key in (
        "production_qualified", "held_out_validation", "false_alert_rate_established",
        "operational_scene_warnings_modified", "media_exported",
        "automatic_reference_reenrollment_or_recovery",
    ):
        require(r.get(key) is False, "Phase3R unsafe source gate " + key)
    for key in ("production_qualified", "media_exported",
                "operational_scene_cues_modified", "camera_physical_reference_approved",
                "incident_recovery_or_reference_rotation"):
        require(s.get(key) is False, "Phase3S unsafe source gate " + key)
    require(r.get("development_reused") is True and
            s.get("development_evidence_not_held_out") is True and
            s.get("prior_phase3r_evidence_reused_without_duplicate_window_evaluation") is True,
            "Input source provenance/staging uncertainty")
    require(set(r.get("days", {})) == set(DAYS) and
            set(s.get("days", {})) == set(DAYS),
            "Require Day3 and Day4 in BOTH numeric reports")
    for day in DAYS:
        original = r["days"][day]
        added = s["days"][day]
        require(original.get("status") == "PHASE3R_SYSTEMATIC_NORMAL_RESEARCH_NOT_HELD_OUT" and
                added.get("status") == "PHASE3S_BALANCED_PRE_EVENT_NUMERIC_RESEARCH_ONLY",
                "Unexpected per-day source status")
        for key in ("source_video_sha256", "source_annotations_sha256"):
            require(isinstance(original.get(key), str) and
                    len(original[key]) == 64 and added.get(key) == original[key],
                    "Mismatch of frozen source video/annotation SHA256: " + key)
        require(original.get("source_reference_is_physical_camera_approved") is False and
                added.get("physical_camera_reference_approved") is False,
                "Reference cannot be approved by this phase")
        require(original.get("scene_raw_review_status_measured") is False and
                original.get("spatial_evidence_status_measured") is False and
                added.get("raw_scene_cues_or_spatial_evidence_measured") is False,
                "Unmeasured raw evidence must remain unknown")
        require(original.get("selected_window_count") == 16 and
                added.get("prior_phase3r_selected_windows") == 16 and
                added.get("prior_phase3r_original_numeric_windows_rereplayed") is False,
                "Expected original 16 windows reused without reprocessing")
        require(original.get("sample_rate_seconds") == 2.0,
                "Sample cadence differs from existing reviewed development data")
        require(added.get("new_pre_event_windows") ==
                len(added.get("new_pre_event_numeric_windows", [])),
                "New Phase3S control denominator mismatch")
        require(added.get("new_pre_event_windows") <= 4 and
                added.get("new_pre_event_windows") >= 0 and
                added.get("sampling_audit", {}).get("all_controls_normal_label_only_not_independently_verified_healthy") is True,
                "Unexpected new pre-event sampling claims")


def _window(day: str, source_phase: str, x: dict) -> dict:
    require(isinstance(x, dict), "Malformed sampled numeric interval")
    start, end = x.get("start_frame"), x.get("end_frame")
    require(type(start) is int and type(end) is int and 0 < start <= end,
            "Invalid numeric case bounds")
    require(x.get("camera_image_healthy_verified") is False and
            x.get("media_exported") is False and
            x.get("production_action_authorized") is False,
            "Source asserts false camera health/production status")
    require(x.get("sampled_positions") == 90 and
            x.get("approx_sampled_time_seconds") == 180.0,
            "Require comparable 180s/2s observation windows")
    policies = x.get("policies")
    require(isinstance(policies, dict) and set(policies) == set(POLICIES),
            "Incomplete research policy evidence")
    stats = {}
    for policy in POLICIES:
        doc = policies[policy]
        require(doc.get("not_verified_false_alerts") is True and
                doc.get("no_incident_created_or_closed") is True,
                "Model reports cannot assert independently verified false alarms")
        starts, active = doc.get("candidate_episode_starts"), doc.get("candidate_active_samples")
        require(_nonnegative_int(starts) and _nonnegative_int(active) and
                starts <= active <= 90 and
                doc.get("candidate_window_has_any_flag") is (active > 0),
                "Candidate episode accounting is inconsistent")
        stats[policy] = {
            "candidate_episode_starts": starts,
            "candidate_active_samples": active,
            "candidate_window_has_any_flag": active > 0,
        }
    confounds = x.get("confounds")
    require(isinstance(confounds, dict) and
            all(isinstance(k, str) and _nonnegative_int(v)
                for k, v in confounds.items()),
            "Malformed confound count metadata")
    require(confounds.get("RAW_SCENE_CUE_NOT_MEASURED", 0) > 0 and
            confounds.get("SPATIAL_EVIDENCE_NOT_MEASURED", 0) > 0,
            "Source evidence cannot be treated as healthy")
    return {
        "day": day, "source_phase": source_phase,
        "start_frame": start, "end_frame": end,
        "stratum_hidden_from_reviewers": x.get("control_stratum"),
        "normal_annotation_not_authentication": True,
        "independent_image_health_truth_available": False,
        "raw_scene_cue_known": False,
        "sampling_control_type_hidden_from_reviewers": x.get("selection"),
        "unresolved_illumination_samples": confounds.get("ILLUMINATION_UNRESOLVED", 0),
        "candidate_policies": stats,
    }


def build_sources(r: dict, s: dict) -> dict[str, list[dict]]:
    _complete_sources(r, s)
    merged = {}
    for day in DAYS:
        original = r["days"][day]["windows"]
        new = s["days"][day]["new_pre_event_numeric_windows"]
        require(len(original) == 16, "Missing Phase3R original windows")
        controls = ([_window(day, "3R", x) for x in original] +
                    [_window(day, "3S", x) for x in new])
        # No camera interval may be counted twice. Even same annotated
        # normal footage under different metadata is double exposure.
        for i, a in enumerate(controls):
            for b in controls[i + 1:]:
                require(a["end_frame"] < b["start_frame"] or
                        b["end_frame"] < a["start_frame"],
                        "Overlapping Phase3R/3S control exposure")
        for policy in POLICIES:
            previous_sum = sum(
                x["candidate_policies"][policy]["candidate_episode_starts"]
                for x in controls if x["source_phase"] == "3R"
            )
            added_sum = sum(
                x["candidate_policies"][policy]["candidate_episode_starts"]
                for x in controls if x["source_phase"] == "3S"
            )
            summary = s["days"][day]["policy_comparison"][policy]
            require(
                summary.get("existing_normal_labeled_candidate_episode_starts") == previous_sum and
                summary.get("new_pre_event_normal_labeled_candidate_episode_starts") == added_sum and
                summary.get("combined_development_sample_candidate_episode_starts") == previous_sum + added_sum and
                summary.get("selected_normal_sample_episode_count_not_false_alert_rate") is True,
                "Upstream Phase3S candidate-episode summary mismatch",
            )
        merged[day] = controls
    return merged


def _select_day(records: list[dict], budget: int) -> list[dict]:
    """All positive controls up to a fixed budget; quantile-match negatives.

    Output is a targeted adjudication sample, NOT a blind random-rate
    estimate. Reviewer is blind to candidate category, not selector.
    """
    require(type(budget) is int and budget >= 2, "Require at least two review slots")
    ordered = sorted(records, key=lambda x: (x["start_frame"], x["end_frame"]))
    positives = [
        x for x in ordered
        if x["candidate_policies"]["sharpness_3_consecutive"]["candidate_window_has_any_flag"]
    ]
    negatives = [
        x for x in ordered
        if not x["candidate_policies"]["sharpness_3_consecutive"]["candidate_window_has_any_flag"]
    ]
    if len(positives) > budget:
        # Deterministic descending candidate burden if resources limited.
        positives = sorted(positives, key=lambda x: (
            -x["candidate_policies"]["sharpness_3_consecutive"]["candidate_episode_starts"],
            -x["candidate_policies"]["sharpness_3_consecutive"]["candidate_active_samples"],
            x["start_frame"],
        ))[:budget]
    slots = min(len(negatives), budget - len(positives))
    if slots:
        indices = [min(len(negatives)-1, int(
            (i+0.5)*len(negatives)/slots)) for i in range(slots)]
        neutral = [negatives[i] for i in indices]
    else:
        neutral = []
    return positives + neutral


def prepare(r: dict, s: dict, *, per_day: int = 10) -> dict:
    merged = build_sources(r, s)
    require(type(per_day) is int and 2 <= per_day <= 20,
            "Review budget must be 2–20 windows per day")
    chosen = []
    candidate_totals = {}
    for day in DAYS:
        sample = _select_day(merged[day], per_day)
        chosen.extend(sample)
        candidate_totals[day] = {
            "available_normal_annotated_controls": len(merged[day]),
            "blind_review_cases": len(sample),
            "source_windows_3r": sum(x["source_phase"] == "3R" for x in sample),
            "source_windows_3s": sum(x["source_phase"] == "3S" for x in sample),
            "three_consecutive_candidate_bearing_cases_hidden_from_reviewers": sum(
                x["candidate_policies"]["sharpness_3_consecutive"]["candidate_window_has_any_flag"]
                for x in sample
            ),
            "three_consecutive_candidate_negative_controls_hidden_from_reviewers": sum(
                not x["candidate_policies"]["sharpness_3_consecutive"]["candidate_window_has_any_flag"]
                for x in sample
            ),
        }
    # Deterministic pseudorandom *order*, not random selection. Sort key is
    # transparent but reviewer-facing CSV has no score/category metadata.
    chosen.sort(key=lambda x: hashlib.sha256(
        f"PHASE3T_V1|{x['day']}|{x['start_frame']}|{x['end_frame']}".encode()
    ).hexdigest())
    sealed = {}
    for index, case in enumerate(chosen, 1):
        case_id = f"KWT3T-{index:03d}"
        sealed[case_id] = case
    review_cases = [{
        "case_id": case_id,
        "video_alias": case["day"].upper(),
        "start_frame": case["start_frame"],
        "end_frame": case["end_frame"],
    } for case_id, case in sealed.items()]
    return {
        "status": "PHASE3T_INDEPENDENT_REVIEW_ASSIGNMENTS_NOT_ADJUDICATED",
        "review_cases": review_cases,
        "sealed_policy_metadata": sealed,
        "selection_audit": {
            "sampled_video_windows_selected_for_manual_review": len(chosen),
            "total_source_windows": sum(map(len, merged.values())),
            "by_day": candidate_totals,
            "enriched_by_previously_inspected_research_candidates": True,
            "unbiased_false_alarm_sample": False,
            "independent_label_truth_available": False,
        },
        "production_qualified": False,
        "review_completed": False,
        "source_footage_exported": False,
        "existing_scene_alerts_modified": False,
        "officer_incident_recovery_authorized": False,
        "source_is_independent_holdout": False,
    }


def write(result: dict, root: Path) -> list[str]:
    require(root.exists() and root.is_dir(),
            "Output directory must already exist")
    paths = {
        "reviewer_01.csv": root / "reviewer_01.csv",
        "reviewer_02.csv": root / "reviewer_02.csv",
        "SEALED_DO_NOT_SHARE_with_reviewers.json":
            root / "SEALED_DO_NOT_SHARE_with_reviewers.json",
    }
    require(all(not path.exists() for path in paths.values()),
            "Refuse to overwrite an existing review or sealed file")
    for reviewer in (1, 2):
        path = paths[f"reviewer_{reviewer:02d}.csv"]
        with path.open("x", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            for sample in result["review_cases"]:
                row = {key: "" for key in FIELDS}
                row.update(sample)
                writer.writerow(row)
    with paths["SEALED_DO_NOT_SHARE_with_reviewers.json"].open(
        "x", encoding="utf-8"
    ) as handle:
        json.dump({
            key: value for key, value in result.items() if key != "review_cases"
        }, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
    return [str(path.resolve()) for path in paths.values()]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase3r-report", type=Path, required=True)
    parser.add_argument("--phase3s-report", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--per-day", type=int, default=10)
    args = parser.parse_args()
    r = json.loads(args.phase3r_report.read_text(encoding="utf-8"))
    s = json.loads(args.phase3s_report.read_text(encoding="utf-8"))
    result = prepare(r, s, per_day=args.per_day)
    paths = write(result, args.out_dir)
    print(json.dumps({
        "status": result["status"],
        "reviewed_windows": result["selection_audit"]["sampled_video_windows_selected_for_manual_review"],
        "selected_case_counts_by_day": result["selection_audit"]["by_day"],
        "files": paths,
        "do_not_send_sealed_key_to_reviewers": True,
        "production_qualified": False,
    }, indent=2))


if __name__ == "__main__":
    main()
