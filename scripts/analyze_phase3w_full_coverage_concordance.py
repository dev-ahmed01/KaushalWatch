#!/usr/bin/env python3
"""Phase 3W source-pinned full-sample *development* scalar concordance.

Independent model candidates from Phase3R/S are contrasted with the
already explored Phase3V sparse sharpness descriptor (ratio below 0.5).
This is NOT held-out performance, false-alarm frequency, physical movement,
camera health, or an approval to adjust thresholds/production incidents.
Raw media is never opened or exported.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from audit_phase3v_container_video_evidence import (
    audit as verify_phase3v, MEASURED,
)

GROUPS = (
    "CANDIDATE_AND_SPARSE_CHANGE",
    "CANDIDATE_WITHOUT_SPARSE_CHANGE",
    "NONCANDIDATE_WITH_SPARSE_CHANGE",
    "NEITHER_RESEARCH_CUE",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def summarize(report: dict, r: dict, s: dict, previous: dict | None = None) -> dict:
    audited = verify_phase3v(report, r, s)
    require(audited["selected_windows"] == 40 and
            audited["windows_with_scalar_video_features"] == 40 and
            audited["windows_without_scalar_video_features"] == 0,
            "Full 40 selected normal-annotated control windows must have scalar AVI evidence")
    coverage = report.get("video_feature_coverage")
    require(isinstance(coverage, dict) and
            coverage.get("selected_windows") == 40 and
            coverage.get("measured_windows") == 40 and
            coverage.get("unmeasured_windows") == 0 and
            coverage.get("sampled_video_frames") == 480 and
            coverage.get("full_selected_window_coverage") is True and
            coverage.get("sampling_is_development_not_physical_truth") is True,
            "Reported 480-frame numeric coverage is not consistent")
    previous_check = {"provided": previous is not None,
                      "previously_sampled_frames_reproduced": None}
    if previous is not None:
        old_audit = verify_phase3v(previous, r, s)
        require(old_audit["windows_with_scalar_video_features"] == 20 and
                old_audit["windows_without_scalar_video_features"] == 20,
                "Expected the former bounded 20-window numeric AVI report")
        old = {x["id"]: x["local_video_evidence"] for x in previous["priority_queue"]
               if x["local_video_evidence"]["status"] == MEASURED}
        new = {x["id"]: x["local_video_evidence"] for x in report["priority_queue"]}
        require(len(old) == 20 and all(new.get(k) == v for k, v in old.items()),
                "Original 20 scalar AVI results changed between runs")
        previous_check = {"provided": True,
                          "previously_sampled_frames_reproduced": True,
                          "previously_sampled_window_count": 20}
    by_day = {}
    focused = []
    proxy_rows = []
    for day in ("day3", "day4"):
        rows = [x for x in report["priority_queue"] if x["day"] == day]
        require(len(rows) == 20, "Expected 20 windows per development day")
        states = Counter()
        geometry_supported = geometry_unknown = supported_pairs = unknown_pairs = 0
        for row in rows:
            video = row["local_video_evidence"]
            require(video["status"] == MEASURED, "An AVI feature window was not measured")
            candidate = row["policies"]["sharpness_3_consecutive"]["window_with_candidate"]
            changed = video["min_laplacian_ratio_to_first_window_frame"] < .5
            state = (GROUPS[0] if candidate and changed else
                     GROUPS[1] if candidate else
                     GROUPS[2] if changed else GROUPS[3])
            states[state] += 1
            supported = video["geometric_proxy_supported_comparisons"]
            unknown = video["geometric_proxy_unknown_comparisons"]
            geometry_supported += int(supported > 0)
            geometry_unknown += int(supported == 0)
            supported_pairs += supported
            unknown_pairs += unknown
            if state != GROUPS[3]:
                focused.append({
                    "day": day, "start_frame": row["start_frame"],
                    "end_frame": row["end_frame"], "research_signal_group": state,
                    "sparse_min_laplacian_ratio": video["min_laplacian_ratio_to_first_window_frame"],
                    "raw_camera_health_independently_verified": False,
                })
            if supported > 0:
                proxy_rows.append({
                    "day": day, "start_frame": row["start_frame"],
                    "end_frame": row["end_frame"], "research_signal_group": state,
                    "max_center_displacement_proxy": video["max_normalized_center_displacement_proxy"],
                    "geometric_pairs_supported": supported,
                    "camera_displacement_physically_verified": False,
                })
        require(sum(states.values()) == 20, "Four research comparison groups must be exhaustive")
        by_day[day] = {
            **{group: states[group] for group in GROUPS},
            "measured_windows": len(rows),
            "geometry_supported_windows": geometry_supported,
            "geometry_unknown_windows": geometry_unknown,
            "geometry_supported_pairs": supported_pairs,
            "geometry_unknown_pairs": unknown_pairs,
        }
    overall = {group: sum(by_day[day][group] for day in by_day) for group in GROUPS}
    require(sum(overall.values()) == 40, "Exactly forty selected control windows required")
    return {
        "status": "PHASE3W_FULL_COVERAGE_RESEARCH_CUES_NOT_PHYSICAL_TRUTH",
        "source_evidence_sha256": report["source_evidence_sha256"],
        "full_video_report_sha256": hashlib.sha256(
            json.dumps(report, sort_keys=True).encode()
        ).hexdigest(),
        "per_day": by_day,
        "overall_concordance": overall,
        "old_run_reproducibility": previous_check,
        "geometry": {
            "windows_with_supported_correspondence": sum(
                x["geometry_supported_windows"] for x in by_day.values()),
            "windows_with_unknown_correspondence": sum(
                x["geometry_unknown_windows"] for x in by_day.values()),
            "supported_comparisons": sum(
                x["geometry_supported_pairs"] for x in by_day.values()),
            "unknown_comparisons": sum(
                x["geometry_unknown_pairs"] for x in by_day.values()),
        },
        "focus_windows_without_person_media": focused,
        "highest_geometry_proxies_not_displacement_truth": sorted(
            proxy_rows,
            key=lambda x: (-x["max_center_displacement_proxy"], x["day"], x["start_frame"])
        )[:5],
        "exploratory_sparse_ratio_cutoff": 0.5,
        "cutoff_is_approved_or_held_out": False,
        "time_aligned_per_sample_comparison": False,
        "normal_annotation_is_verified_healthy_image": False,
        "physical_camera_tampering_proven": False,
        "field_false_alarm_rate_established": False,
        "production_qualified": False,
        "model_tuned_or_alert_policy_changed": False,
        "media_or_camera_frames_exported": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--phase3r", required=True, type=Path)
    parser.add_argument("--phase3s", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    if args.out.suffix.lower() != ".json" or args.out.exists():
        parser.error("Output must be an unused JSON file")
    def read(path):
        return json.loads(path.read_text(encoding="utf-8"))
    result = summarize(
        read(args.report), read(args.phase3r), read(args.phase3s),
        read(args.previous) if args.previous else None
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
    print(json.dumps({
        "status": result["status"],
        "overall_concordance": result["overall_concordance"],
        "geometry": result["geometry"],
        "production_qualified": False,
        "out": str(args.out),
    }, indent=2))


if __name__ == "__main__":
    main()
