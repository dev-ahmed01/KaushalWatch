#!/usr/bin/env python3
"""Phase 3Q: numeric-only counterfactuals on completed Phase 3P evidence.

No footage, annotation-guided decisions, detector replay, reference reset,
incident action, threshold selection, or production integration. Existing
annotation labels are used ONLY in post-hoc event/window accounting.
All policies are exploratory and never authorized to change a real alert.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path
from statistics import median

INPUT_STATUS = "PHASE3P_BOUNDED_TWO_DAY_CAUSAL_NUMERIC_EVIDENCE_ONLY"
WINDOW_STATUS = "PHASE3P_BOUNDED_CAUSAL_DEVELOPMENT_REPLAY_NOT_HELD_OUT"
STATES = frozenset((
    "INSUFFICIENT_PAST_SAMPLE_COVERAGE",
    "NONINFORMATIVE_PAST_DENOMINATOR_ABSTAIN",
    "PAIRED_UNVERIFIED_NUMERIC_OBSERVATION",
    "UNKNOWN_LOW_TEXTURE_ABSTAIN",
    "REFERENCE_TEXTURE_INSUFFICIENT_ABSTAIN",
    "DISCONTINUOUS_HISTORY",
))
KINDS = ("defocused", "moved", "normal_control")
HYPOTHESES = frozenset((
    "ILLUMINATION_CONFOUNDED", "NO_SHARPNESS_LOSS_SIGNAL",
    "SHARPNESS_LOSS_COMPATIBLE", "REFERENCE_TEXTURE_INSUFFICIENT",
))
CUTOFF = 0.5  # Frozen from previously inspected exploratory work; NOT calibrated.
LOOKBACK_SECONDS = 30.0
POLICIES = (
    "phase3p_original_unmodified",
    "sharpness_only_numeric",
    "sharpness_2_of_previous_3",
    "sharpness_3_consecutive",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def finite_nonnegative(x: object) -> bool:
    return type(x) in (int, float) and math.isfinite(x) and x >= 0


def _valid_report(report: dict) -> dict:
    require(isinstance(report, dict) and report.get("status") == INPUT_STATUS,
            "Only full completed Phase3P two-day numeric report is accepted")
    for flag in ("all_video_frames_replayed", "automatic_reference_reset_or_recovery",
                 "media_exported", "operational_alerts_modified", "production_qualified"):
        require(report.get(flag) is False, "Phase3P release gate mismatch: " + flag)
    days = report.get("days")
    require(isinstance(days, dict) and set(days) == {"day3", "day4"},
            "Require both Phase3P development days")
    return days


def _window_samples(day: str, window: dict, step_seconds: float) -> list[dict]:
    kind = window.get("kind")
    require(kind in KINDS, "Unexpected window type")
    require(window.get("frames_or_media_exported") is False,
            "Source window media-export assertion failed")
    source = window.get("samples")
    require(isinstance(source, list) and len(source) > 0, "Missing sampled window")
    require(finite_nonnegative(window.get("sample_seconds_requested")) and
            abs(window["sample_seconds_requested"] - step_seconds) < 1e-8,
            "Window sample rate differs from pinned day rate")
    start = window.get("start_frame")
    end = window.get("end_frame")
    require(type(start) is int and type(end) is int and 1 <= start <= end,
            "Invalid window frame boundaries")
    target = window.get("target_event_start_frame")
    target_end = window.get("target_event_end_frame")
    if kind != "normal_control":
        require(type(target) is int and type(target_end) is int and
                start <= target <= target_end, "Malformed target event positions")
    else:
        require(target is None and target_end is None,
                "Normal control cannot have target event")
    seen = set()
    for item in source:
        require(isinstance(item, dict), "Malformed sample record")
        n = item.get("sample_frame")
        require(type(n) is int and start <= n <= end and n not in seen,
                "Invalid or repeated sampled frame position")
        seen.add(n)
        require(item.get("comparison_state") in STATES,
                "Unknown historical comparison state")
        require(item.get("quality_hypothesis") in HYPOTHESES,
                "Unknown quality status")
        value = item.get("sharpness_relative_to_unchanged_fixed_reference")
        require(finite_nonnegative(value), "Missing or nonfinite fixed-reference sharpness")
        require(item.get("annotation_class_for_posthoc_evaluation_only") in
                ("normal", "covered", "defocused", "moved"),
                "Missing posthoc label")
        assert_flag = item.get("exploratory_drop_0_5")
        ratio = item.get("paired_sharpness_ratio")
        if ratio is None:
            require(assert_flag is None, "Missing ratio must have unknown original flag")
            require(item["comparison_state"] != "PAIRED_UNVERIFIED_NUMERIC_OBSERVATION",
                    "Paired state cannot omit ratio")
        else:
            require(finite_nonnegative(ratio) and type(assert_flag) is bool,
                    "Original ratio/flag mismatch")
            require((ratio <= CUTOFF) is assert_flag,
                    "Original causal flag differs from pinned ratio")
            require(item["comparison_state"] == "PAIRED_UNVERIFIED_NUMERIC_OBSERVATION",
                    "Original ratio present without valid paired state")
        confounds = item.get("confounds")
        require(isinstance(confounds, list) and
                all(isinstance(c, str) for c in confounds),
                "Require explicit unresolved confounds list")
        if ratio is not None:
            require("RAW_SCENE_CUE_NOT_MEASURED" in confounds and
                    "SPATIAL_EVIDENCE_NOT_MEASURED" in confounds,
                    "Unknown raw scene/quality evidence must stay visible")
    require(all(source[i]["sample_frame"] < source[i+1]["sample_frame"]
                for i in range(len(source)-1)), "Nonmonotonic window frames")
    return source


def _counterfactual_flags(samples: list[dict], step_seconds: float) -> tuple[dict, dict]:
    # Compare exactly 30 seconds into the past. No annotation input here.
    lag_float = LOOKBACK_SECONDS / step_seconds
    require(abs(lag_float - round(lag_float)) < 1e-8,
            "Lookback must align with observed Phase3P sample cadence")
    lag = int(round(lag_float))
    flags = {policy: [] for policy in POLICIES}
    observation_counts = Counter()
    raw = []
    for i, sample in enumerate(samples):
        original = sample["exploratory_drop_0_5"] is True
        flags["phase3p_original_unmodified"].append(original)
        ratio = None
        if i >= lag:
            before = samples[i-lag]
            # This is the causal quality sharpness axis alone, NOT an
            # independently healthy reference or detector/incident state.
            # Preserve all other unknowns, don't silently make them healthy.
            old = before["sharpness_relative_to_unchanged_fixed_reference"]
            cur = sample["sharpness_relative_to_unchanged_fixed_reference"]
            source_abstain = sample["comparison_state"] in (
                "UNKNOWN_LOW_TEXTURE_ABSTAIN",
                "REFERENCE_TEXTURE_INSUFFICIENT_ABSTAIN",
                "DISCONTINUOUS_HISTORY",
            ) or before["comparison_state"] in (
                "UNKNOWN_LOW_TEXTURE_ABSTAIN",
                "REFERENCE_TEXTURE_INSUFFICIENT_ABSTAIN",
                "DISCONTINUOUS_HISTORY",
            )
            if (old > 1e-6 and not source_abstain and
                before["quality_hypothesis"] != "REFERENCE_TEXTURE_INSUFFICIENT" and
                sample["quality_hypothesis"] != "REFERENCE_TEXTURE_INSUFFICIENT"):
                ratio = cur / old
            if sample["paired_sharpness_ratio"] is not None:
                require(ratio is not None and
                        abs(ratio - sample["paired_sharpness_ratio"]) <= 2e-5,
                        "Reconstructed paired ratio disagrees with Phase3P")
            if ratio is not None and sample["paired_sharpness_ratio"] is None:
                observation_counts["sharpness_available_despite_combined_abstention"] += 1
        if ratio is not None:
            observation_counts["sharpness_only_numeric_eligible"] += 1
        else:
            observation_counts["sharpness_only_numeric_abstain"] += 1
        trigger = ratio is not None and ratio <= CUTOFF
        raw.append(trigger)
        flags["sharpness_only_numeric"].append(trigger)
        flags["sharpness_2_of_previous_3"].append(
            i >= 2 and sum(raw[i-2:i+1]) >= 2
        )
        flags["sharpness_3_consecutive"].append(
            i >= 2 and all(raw[i-2:i+1])
        )
    return flags, dict(observation_counts)


def _policy_window_scores(kind: str, samples: list[dict], flags: list[bool]) -> dict:
    require(len(flags) == len(samples), "Candidate flag count mismatch")
    target_indices = [
        i for i, sample in enumerate(samples)
        if kind != "normal_control" and
        sample["annotation_class_for_posthoc_evaluation_only"] == kind and
        sample.get("offset_from_target_start_seconds_for_posthoc_analysis") is not None and
        sample["offset_from_target_start_seconds_for_posthoc_analysis"] >= 0
    ]
    normal_indices = [
        i for i, sample in enumerate(samples)
        if sample["annotation_class_for_posthoc_evaluation_only"] == "normal"
    ]
    episode_starts = [
        i for i, flag in enumerate(flags)
        if flag and (i == 0 or not flags[i-1])
    ]
    initial_target_index = target_indices[0] if target_indices else None
    warning_preexisting = (
        bool(initial_target_index is not None and initial_target_index > 0 and
             flags[initial_target_index - 1])
    )
    target_candidate_indices = [i for i in target_indices if flags[i]]
    fresh_target_indices = [i for i in episode_starts if i in set(target_indices)]
    first = (
        samples[fresh_target_indices[0]][
            "offset_from_target_start_seconds_for_posthoc_analysis"
        ] if fresh_target_indices else None
    )
    any_first = (
        samples[target_candidate_indices[0]][
            "offset_from_target_start_seconds_for_posthoc_analysis"
        ] if target_candidate_indices else None
    )
    return {
        "target_event_samples": len(target_indices),
        "target_samples_candidate_active": len(target_candidate_indices),
        "has_candidate_during_target": bool(target_candidate_indices),
        "candidate_preexisting_at_target_onset": warning_preexisting,
        "fresh_candidate_during_target": bool(fresh_target_indices),
        "first_fresh_candidate_offset_s": first,
        "first_any_candidate_offset_s": any_first,
        "normal_annotated_samples": len(normal_indices),
        "annotated_normal_samples_candidate_active": sum(flags[i] for i in normal_indices),
        "candidate_episodes_start_annotated_normal": sum(
            i in set(normal_indices) for i in episode_starts
        ),
        "window_contains_any_candidate": any(flags),
        "counterfactual_numeric_episode_starts": len(episode_starts),
        "candidate_only_never_operational_incident": True,
    }


def _aggregate(windows: list[dict], policy: str) -> dict:
    summary = {}
    for kind in KINDS:
        relevant = [w for w in windows if w["kind"] == kind]
        statuses = [w["candidate_scores"][policy] for w in relevant]
        onset = [s["first_fresh_candidate_offset_s"] for s in statuses
                 if s["first_fresh_candidate_offset_s"] is not None]
        summary[kind] = {
            "selected_windows": len(relevant),
            "windows_with_any_candidate": sum(s["window_contains_any_candidate"] for s in statuses),
            "windows_with_any_candidate_during_target": sum(s["has_candidate_during_target"] for s in statuses),
            "windows_with_fresh_candidate_during_target": sum(s["fresh_candidate_during_target"] for s in statuses),
            "windows_preexisting_candidate_at_event_onset": sum(
                s["candidate_preexisting_at_target_onset"] for s in statuses
            ),
            "annotated_normal_candidate_active_samples": sum(
                s["annotated_normal_samples_candidate_active"] for s in statuses
            ),
            "annotated_normal_candidate_episode_starts": sum(
                s["candidate_episodes_start_annotated_normal"] for s in statuses
            ),
            "median_first_fresh_candidate_s_when_present": (
                round(median(onset), 3) if onset else None
            ),
            "first_fresh_candidate_offsets_s": onset,
            "no_full_day_false_positive_or_recall_inference": True,
        }
    return summary


def analyze(report: dict) -> dict:
    days = _valid_report(report)
    outputs = {}
    all_windows = []
    combined_abstain = Counter()
    for name in ("day3", "day4"):
        day = days[name]
        require(isinstance(day, dict) and day.get("status") == WINDOW_STATUS,
                "Wrong Phase3P day status")
        for flag in ("production_qualified", "reference_is_approved",
                     "source_is_held_out", "full_day_detector_replayed",
                     "scene_raw_review_status_measured",
                     "spatial_evidence_status_measured",
                     "automatic_reference_reset_or_recovery",
                     "video_or_images_exported"):
            require(day.get(flag) is False, "Day release/missing-evidence mismatch: "+flag)
        step = day.get("sample_rate_seconds")
        require(finite_nonnegative(step) and step > 0 and step <= 5,
                "Invalid numeric sample interval")
        windows = day.get("windows")
        require(isinstance(windows, list) and windows, "No selected windows to score")
        scored = []
        for w in windows:
            samples = _window_samples(name, w, step)
            flags, coverage = _counterfactual_flags(samples, step)
            combined_abstain.update(coverage)
            scored.append({
                "day": name,
                "kind": w["kind"],
                "start_frame": w["start_frame"],
                "end_frame": w["end_frame"],
                "target_event_start_frame": w["target_event_start_frame"],
                "input_samples": len(samples),
                "numeric_coverage": coverage,
                "candidate_scores": {
                    policy: _policy_window_scores(w["kind"], samples, values)
                    for policy, values in flags.items()
                },
            })
        expected = day.get("summary")
        require(isinstance(expected, dict), "Missing source summary")
        for kind in KINDS:
            count = sum(w["kind"] == kind for w in scored)
            require(isinstance(expected.get(kind), dict) and
                    count == expected[kind].get("selected_windows"),
                    "Selected window denominator mismatch")
        outputs[name] = {
            "windows_evaluated": len(scored),
            "policies": {policy: _aggregate(scored, policy) for policy in POLICIES},
        }
        all_windows.extend(scored)
    return {
        "status": "PHASE3Q_NUMERIC_COUNTERFACTUAL_RESEARCH_NOT_HELD_OUT",
        "source_status": INPUT_STATUS,
        "policy_names": list(POLICIES),
        "frozen_exploratory_cutoff": CUTOFF,
        "lookback_seconds": LOOKBACK_SECONDS,
        "sampled_windows_total": len(all_windows),
        "numeric_coverage_all_windows": dict(combined_abstain),
        "days": outputs,
        "pooled_policies": {
            policy: _aggregate(all_windows, policy) for policy in POLICIES
        },
        "numeric_per_window_scoring": all_windows,
        "original_scene_warning_cues_modified": False,
        "real_incident_status_or_notification_modified": False,
        "threshold_tuned_or_selected": False,
        "production_qualified": False,
        "held_out_test": False,
        "camera_source_reference_approved": False,
        "media_exported": False,
        "limitations": [
            "All candidate rules are retrospective exploratory development comparisons, never production decisions",
            "Policies process only numeric causal features; annotations are used after-the-fact for accounting",
            "Original scene cues/spatial evidence are NOT_MEASURED, not healthy or false",
            "No independent camera physical reference or blinded quality ground truth exists",
            "A zero denominator on one quality axis does not make all sharpness evidence unusable",
            "Paired sharpness can return toward one during prolonged defocus; this is NOT recovery",
            "Original quality observer's paired status does not certify genuine image usability",
            "Development event windows and four controls are not representative of complete normal footage",
            "Original four candidate normal controls failed annotation-screening and were omitted",
            "A candidate episode ending is not operator-approved incident closure or reference re-enrollment",
            "Cutoff 0.5 and consecutive windows were inspected on development data; not preregistered",
            "No operational false-positive rate, precision, recall, field latency, or release approval",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.suffix.lower() != ".json" or args.out.exists():
        parser.error("Provide a new unused .json output path")
    if args.input.resolve() == args.out.resolve():
        parser.error("Cannot overwrite source report")
    source = json.loads(args.input.read_text(encoding="utf-8"))
    result = analyze(source)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "sampled_windows_total": result["sampled_windows_total"],
        "numeric_coverage": result["numeric_coverage_all_windows"],
        "output": str(args.out.resolve()),
        "production_qualified": False,
    }, indent=2))


if __name__ == "__main__":
    main()
