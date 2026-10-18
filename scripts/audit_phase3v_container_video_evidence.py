#!/usr/bin/env python3
"""Phase 3V: audit scalar AVI evidence exported from the isolated workstation.

Does NOT read recordings and does NOT validate physical camera health.
Checks that sparse scalar features and policy summaries preserve the identity,
window selection, missingness and 'unverified' safeguards of Phase3R/3S.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

from prepare_phase3t_blinded_reviews import build_sources, POLICIES

RESEARCH_STATUS = "OFFLINE_DEVELOPMENT_EVIDENCE_ANALYZED_NO_PHYSICAL_TRUTH"
MEASURED = "UNVERIFIED_LOCAL_VIDEO_FEATURES_NOT_GROUND_TRUTH"
BUDGET = "NOT_SELECTED_FOR_BOUNDED_VIDEO_SAMPLING"
LEGACY_MISSING = "SOURCE_VIDEO_NOT_MOUNTED"


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def _number(value, low=0, high=None) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value >= low and (
        high is None or value <= high)


def _raw_hash(r: dict, s: dict) -> str:
    return hashlib.sha256(
        (json.dumps(r, sort_keys=True) + "\n" +
         json.dumps(s, sort_keys=True)).encode()
    ).hexdigest()


def audit(report: dict, r: dict, s: dict) -> dict:
    merged = build_sources(r, s)  # Fail closed for source SHA/unknown evidence.
    require(isinstance(report, dict) and report.get("status") == RESEARCH_STATUS,
            "Unexpected scalar video evidence report status")
    for claim in ("production_qualified", "independent_camera_authentication",
                  "false_alarm_rate_known", "incident_recovery_authorized"):
        require(report.get(claim) is False, "Report must not assert physical/operational truth: " + claim)
    require(report.get("source_evidence_sha256") == _raw_hash(r, s),
            "Source Phase3R/3S evidence checksum mismatch")
    pins = report.get("source_pins")
    require(isinstance(pins, dict) and set(pins) == {"day3", "day4"},
            "Missing two-day source pin coverage")
    by_day = report.get("by_day")
    require(isinstance(by_day, dict) and set(by_day) == {"day3", "day4"},
            "Missing two-day episode summary")
    expected = {}
    for day in ("day3", "day4"):
        ref = r["days"][day]
        pin = pins[day]
        require(pin.get("video_sha256") == ref["source_video_sha256"] and
                pin.get("annotations_sha256") == ref["source_annotations_sha256"] and
                pin.get("unapproved_development_reference_sha256") ==
                ref["frozen_unapproved_reference_pixel_sha256"],
                "Pinned video/annotation/reference SHA mismatch")
        expected.update({
            f"{day}-{w['start_frame']}-{w['end_frame']}": w
            for w in merged[day]
        })
        source_window_count = len(merged[day])
        by = by_day[day]
        require(by.get("window_count") == source_window_count and
                by.get("selected_normal_labeled_hours") == source_window_count * 180 / 3600,
                "Per-day sampled exposure mismatch")
        for policy in POLICIES:
            summarized = by["policy_candidates"][policy]
            records = merged[day]
            require(
                summarized.get("candidate_episode_starts") ==
                sum(x["candidate_policies"][policy]["candidate_episode_starts"]
                    for x in records) and
                summarized.get("candidate_active_samples") ==
                sum(x["candidate_policies"][policy]["candidate_active_samples"]
                    for x in records) and
                summarized.get("windows_with_numeric_candidate") ==
                sum(x["candidate_policies"][policy]["candidate_window_has_any_flag"]
                    for x in records) and
                summarized.get("verified_false_alarms") is None,
                "Per-day candidate counts or false-alarm claims corrupted",
            )
    rows = report.get("priority_queue")
    require(isinstance(rows, list) and len(rows) == len(expected) and
            report.get("number_of_windows") == len(expected) and
            report.get("selected_normal_labeled_hours") == len(expected) * 180 / 3600,
            "Video report window denominator mismatch")
    observed = [x.get("id") for x in rows if isinstance(x, dict)]
    require(len(observed) == len(rows) and len(set(observed)) == len(rows) and
            set(observed) == set(expected), "Missing, duplicate or unknown control windows")
    result = {}
    for day in ("day3", "day4"):
        result[day] = {
            "selected_windows": len(merged[day]),
            "video_features_measured": 0,
            "video_windows_not_measured": 0,
            "video_frames_decoded": 0,
            "persistent_candidate_windows_measured": 0,
            "persistent_candidate_windows_unmeasured": 0,
            "sharpness_proxy_change_on_candidate_windows": 0,
            "sharpness_proxy_change_on_comparator_windows": 0,
            "geometry_unknown_on_measured_windows": 0,
        }
    legacy_budget_skips = 0
    for item in rows:
        key = item["id"]
        original = expected[key]
        day = original["day"]
        require(item.get("day") == day and
                item.get("start_frame") == original["start_frame"] and
                item.get("end_frame") == original["end_frame"] and
                item.get("source_phase") == original["source_phase"] and
                item.get("stratum") == original["stratum_hidden_from_reviewers"] and
                item.get("physical_condition_verified") is False and
                item.get("independent_ground_truth") is False,
                "Source window identity or camera-health claim changed")
        for policy in POLICIES:
            p = item.get("policies", {}).get(policy, {})
            source = original["candidate_policies"][policy]
            require(p.get("episodes") == source["candidate_episode_starts"] and
                    p.get("active_samples") == source["candidate_active_samples"] and
                    p.get("window_with_candidate") ==
                    source["candidate_window_has_any_flag"],
                    "Numeric candidate counts changed")
        win = item.get("local_video_evidence")
        require(isinstance(win, dict) and
                win.get("status") in (MEASURED, BUDGET, LEGACY_MISSING) and
                win.get("physical_camera_health_verified") is False and
                win.get("has_independent_visual_truth") is False,
                "Invalid physical source-video evidence status")
        daily = result[day]
        is_candidate = original["candidate_policies"]["sharpness_3_consecutive"][
            "candidate_window_has_any_flag"
        ]
        if win["status"] != MEASURED:
            daily["video_windows_not_measured"] += 1
            daily["persistent_candidate_windows_unmeasured"] += int(is_candidate)
            legacy_budget_skips += int(win["status"] == LEGACY_MISSING)
            continue
        require(win.get("video_or_frames_exported") is False and
                win.get("camera_tamper_event_proven") is False and
                win.get("scene_incident_or_recovery_changed") is False and
                win.get("approved_camera_reference_used") is False and
                win.get("feature_cutoff_not_production_approved") is True and
                win.get("scene_geometry_proxy_not_camera_displacement_truth") is True,
                "Unsupported production/tamper claims in scalar evidence")
        frames = win.get("sampled_source_frames")
        require(type(frames) is int and 4 <= frames <= 48 and
                win.get("first_sample_frame") == original["start_frame"] and
                win.get("last_sample_frame") == original["end_frame"],
                "Video frame bounds or sample count mismatch")
        for value in ("first_frame_laplacian_variance",
                      "last_frame_laplacian_variance",
                      "min_laplacian_ratio_to_first_window_frame"):
            require(_number(win.get(value)), "Invalid sharpness statistic")
        ratio = win["min_laplacian_ratio_to_first_window_frame"]
        require(ratio <= 1.00001, "Minimum window sharpness ratio exceeds baseline")
        for value in ("max_luma_delta_between_sparse_samples", "mean_luma_range"):
            require(_number(win.get(value), high=255), "Invalid luma statistic")
        supported = win.get("geometric_proxy_supported_comparisons")
        unknown = win.get("geometric_proxy_unknown_comparisons")
        require(type(supported) is int and type(unknown) is int and
                0 <= supported <= frames-1 and
                0 <= unknown <= frames-1 and
                supported+unknown == frames-1,
                "Unknown geometry comparisons incorrectly treated as supported")
        displacement = win.get("max_normalized_center_displacement_proxy")
        require((supported == 0 and displacement is None) or
                (supported > 0 and _number(displacement)),
                "Geometry displacement metadata mismatched")
        changed = ratio < 0.5
        require(win.get("derived_sparse_feature_assessment") == (
            "SUBSTANTIAL_SPARSE_SHARPNESS_CHANGE_POSSIBLE" if changed else
            "NO_LARGE_SPARSE_SHARPNESS_CHANGE_OBSERVED"
        ), "Exploratory feature label does not agree with reported ratio")
        daily["video_features_measured"] += 1
        daily["video_frames_decoded"] += frames
        daily["persistent_candidate_windows_measured"] += int(is_candidate)
        daily["geometry_unknown_on_measured_windows"] += int(supported == 0)
        if changed:
            feature = ("sharpness_proxy_change_on_candidate_windows"
                       if is_candidate else "sharpness_proxy_change_on_comparator_windows")
            daily[feature] += 1
    sampled = sum(x["video_features_measured"] for x in result.values())
    require(report.get("recordings_available_in_workspace") is (sampled > 0),
            "Video mount/measurement availability contradiction")
    return {
        "status": "PHASE3V_IMPORTED_VIDEO_RESEARCH_AUDIT_ONLY",
        "source_evidence_sha256": report["source_evidence_sha256"],
        "selected_windows": len(rows),
        "windows_with_scalar_video_features": sampled,
        "windows_without_scalar_video_features": len(rows) - sampled,
        "source_video_sha_recomputed_during_this_report_audit": False,
        "legacy_windows_mislabeled_video_not_mounted_despite_sampler_budget": (
            legacy_budget_skips if sampled else 0
        ),
        "per_day": result,
        "normal_annotation_independent_camera_health_truth": False,
        "field_false_alert_rate_established": False,
        "production_qualified": False,
        "recommendation": (
            "Repeat bounded 12-frame AVI feature analysis over all 40 selected windows "
            "using the frozen source SHAs; do not tune operational warning thresholds"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--phase3r", type=Path, required=True)
    parser.add_argument("--phase3s", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.suffix.lower() != ".json" or args.out.exists():
        parser.error("Output must be an unused JSON file")
    result = audit(
        json.loads(args.evidence.read_text(encoding="utf-8")),
        json.loads(args.phase3r.read_text(encoding="utf-8")),
        json.loads(args.phase3s.read_text(encoding="utf-8")),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
    print(json.dumps({
        "status": result["status"],
        "measured": result["windows_with_scalar_video_features"],
        "missing": result["windows_without_scalar_video_features"],
        "production_qualified": False,
        "out": str(args.out),
    }, indent=2))


if __name__ == "__main__":
    main()
