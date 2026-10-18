#!/usr/bin/env python3
"""Phase 3R: systematic annotated-normal sampling, offline numeric research only.

Sample across the time distribution and pre/post-event normal intervals on
the previously verified Phase3M Day3/Day4 videos. Every control window is
normal *according to provided labels only*; camera health and physical
reference provenance remain UNVERIFIED. Selection depends ONLY on existing
annotations and predeclared time bins, never visibility, score or candidate
warnings. The causal observer sees past numeric features only.

No frame/image/media export, full-day detector replay, changed scene reviews,
operational incidents, recovery or threshold tuning.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.camera_visibility_quality_shadow import VisibilityQualityShadow  # noqa: E402
from run_phase3p_bounded_causal_quality import _verify_day, _replay_window  # noqa: E402
from analyze_phase3q_numeric_continuity import (  # noqa: E402
    _counterfactual_flags, POLICIES, CUTOFF,
)

STATUS = "PHASE3R_SYSTEMATIC_NORMAL_RESEARCH_NOT_HELD_OUT"


def _normal_runs(labels: np.ndarray) -> list[tuple[int, int]]:
    """Inclusive 1-based runs; no image feature or detector output involved."""
    if (not isinstance(labels, np.ndarray) or labels.ndim != 1 or
            labels.dtype != np.uint8):
        raise ValueError("Expected canonical one-dimensional uint8 labels")
    normal = labels == 0
    starts = np.flatnonzero(normal & ~np.r_[False, normal[:-1]]) + 1
    ends = np.flatnonzero(normal & ~np.r_[normal[1:], False]) + 1
    return list(zip(starts.tolist(), ends.tolist()))


def _overlap(left: dict, right: dict) -> bool:
    return (left["start_frame"] <= right["end_frame"]
            and right["start_frame"] <= left["end_frame"])


def _quantile_indices(total: int, take: int) -> list[int]:
    if type(total) is not int or type(take) is not int or total < 0 or take < 0:
        raise ValueError("Nonnegative integer quantile counts required")
    count = min(total, take)
    return [min(total - 1, int((i + 0.5) * total / count))
            for i in range(count)]


def _make_normal_spec(start: int, end: int, *, source: str, stratum: str) -> dict:
    return {
        "kind": "normal_control",
        "start_frame": int(start), "end_frame": int(end),
        "target_event_start_frame": None,
        "target_event_end_frame": None,
        "selection": source,
        "control_stratum": stratum,
        "physical_camera_healthy_verified": False,
    }


def choose_controls(
    labels: np.ndarray, events: list[dict], *, fps: float,
    window_seconds: int = 180, time_bins: int = 12, adjacent_each: int = 4,
) -> tuple[list[dict], dict]:
    """Deterministic, label-conditioned coverage sampling with audit of misses.

    First choose closest eligible fully-normal interval to each fixed time-bin
    midpoint (whole interval must fit *inside* bin). Then choose at most
    adjacent_each windows immediately BEFORE and AFTER event boundaries.
    Reject any overlaps to avoid double counting sampled time. The
    selection is NOT random and cannot estimate unobserved false alarms.
    """
    if (not isinstance(labels, np.ndarray) or labels.ndim != 1 or
            labels.dtype != np.uint8 or len(labels) < 1 or
            not np.isfinite(fps) or fps <= 0 or
            type(window_seconds) is not int or not 90 <= window_seconds <= 600 or
            type(time_bins) is not int or not 2 <= time_bins <= 32 or
            type(adjacent_each) is not int or not 0 <= adjacent_each <= 12):
        raise ValueError("Invalid bounded normal-control sampling parameters")
    total = len(labels)
    span = max(1, round(window_seconds * fps))
    runs = _normal_runs(labels)
    controls: list[dict] = []
    bins = []
    for b in range(time_bins):
        low = 1 + (b * total // time_bins)
        high = (b + 1) * total // time_bins
        middle = (low + high) / 2
        compatible = []
        frames_normal = 0
        for run_start, run_end in runs:
            left, right = max(low, run_start), min(high, run_end)
            if left > right:
                continue
            frames_normal += right - left + 1
            if right - left + 1 < span:
                continue
            proposed = int(round(middle - (span - 1) / 2))
            proposed = min(max(proposed, left), right - span + 1)
            compatible.append((
                abs((proposed + (span - 1) / 2) - middle),
                proposed,
            ))
        metadata = {
            "stratum": f"progress_{b+1:02d}_of_{time_bins:02d}",
            "stratum_start_frame": low, "stratum_end_frame": high,
            "annotated_normal_frames": frames_normal,
            "stratum_total_frames": high - low + 1,
            "eligible_full_windows": len(compatible),
            "selected": bool(compatible),
            "not_day_night_or_wallclock_time": True,
        }
        if compatible:
            _, start = min(compatible)
            controls.append(_make_normal_spec(
                start, start + span - 1, source="fixed_progress_strata",
                stratum=metadata["stratum"],
            ))
        else:
            metadata["skip_reason"] = "no_contiguous_annotated_normal_span_inside_bin"
        bins.append(metadata)

    adjacency = {}
    for direction in ("before", "after"):
        candidates = []
        for event in events:
            if event.get("kind") not in (1, 2, 3):
                raise ValueError("Unexpected annotated event kind")
            if direction == "before":
                start = int(event["start_frame"]) - span
                end = int(event["start_frame"]) - 1
            else:
                start = int(event["end_frame"]) + 1
                end = int(event["end_frame"]) + span
            if start < 1 or end > total:
                continue
            if np.any(labels[start-1:end] != 0):
                continue
            candidates.append((start, end, int(event["start_frame"]),
                               int(event["end_frame"])))
        # Remove repeats caused by two events sharing the same control
        # interval; selection remains based on annotation structure alone.
        candidates = list(dict.fromkeys(candidates))
        selected = 0
        conflicts = 0
        for idx in _quantile_indices(len(candidates), adjacent_each):
            start, end, event_start, event_end = candidates[idx]
            spec = _make_normal_spec(
                start, end, source="annotation_event_adjacent",
                stratum=f"{direction}_event_{event_start}_{event_end}",
            )
            if any(_overlap(spec, previous) for previous in controls):
                conflicts += 1
                continue
            controls.append(spec)
            selected += 1
        adjacency[direction] = {
            "fully_normal_eligible_candidates": len(candidates),
            "predeclared_quantile_candidates": min(len(candidates), adjacent_each),
            "selected_nonoverlapping": selected,
            "rejected_overlap": conflicts,
            "source_is_label_conditioned_not_blinded": True,
        }

    for selected in controls:
        start, end = selected["start_frame"], selected["end_frame"]
        if end - start + 1 != span or np.any(labels[start-1:end] != 0):
            raise ValueError("A selected normal control includes non-normal labels")
    for i, first in enumerate(controls):
        for second in controls[i+1:]:
            if _overlap(first, second):
                raise ValueError("Duplicated coverage in selected windows")
    return controls, {
        "sampling_design": "fixed_progress_bins_then_label_eligible_event_adjacency",
        "window_seconds": window_seconds, "window_frames": span,
        "planned_time_bins": time_bins,
        "planned_event_adjacency_each_direction": adjacent_each,
        "selected_windows": len(controls),
        "selected_time_strata": sum(x["selected"] for x in bins),
        "unfilled_time_strata": sum(not x["selected"] for x in bins),
        "time_strata": bins,
        "event_adjacency": adjacency,
        "normal_labeled_not_authenticated_camera_healthy": True,
        "no_random_or_unbiased_sampling_claim": True,
    }


def _episode_metrics(flags: list[bool], step_seconds: float) -> dict:
    starts = [i for i, value in enumerate(flags)
              if value and (i == 0 or not flags[i-1])]
    run_lengths = []
    for first in starts:
        last = first
        while last + 1 < len(flags) and flags[last+1]:
            last += 1
        run_lengths.append(last - first + 1)
    return {
        "candidate_episode_starts": len(starts),
        "candidate_active_samples": sum(flags),
        "approx_candidate_active_sample_seconds": round(step_seconds * sum(flags), 3),
        "longest_candidate_contiguous_samples": max(run_lengths, default=0),
        "candidate_window_has_any_flag": any(flags),
        "not_verified_false_alerts": True,
        "no_incident_created_or_closed": True,
    }


def _summarize_window(window: dict, step_seconds: float) -> dict:
    samples = window["samples"]
    if (not samples or any(sample.get(
            "annotation_class_for_posthoc_evaluation_only") != "normal"
            for sample in samples)):
        raise ValueError("Selected all-normal control has inconsistent decoded sample labels")
    policies, coverage = _counterfactual_flags(samples, step_seconds)
    counter = Counter(item["comparison_state"] for item in samples)
    hypotheses = Counter(item["quality_hypothesis"] for item in samples)
    confounds = Counter(x for item in samples for x in item["confounds"])
    return {
        "selection": window["selection"],
        "control_stratum": window["control_stratum"],
        "start_frame": window["start_frame"],
        "end_frame": window["end_frame"],
        "sampled_positions": len(samples),
        "approx_sampled_time_seconds": round(len(samples) * step_seconds, 3),
        "paired_numeric_coverage": coverage,
        "comparison_states": dict(counter),
        "quality_hypotheses": dict(hypotheses),
        "confounds": dict(confounds),
        "policies": {name: _episode_metrics(flags, step_seconds)
                     for name, flags in policies.items()},
        "camera_image_healthy_verified": False,
        "media_exported": False,
        "production_action_authorized": False,
    }


def run_day(
    *, video: Path, annotations: Path, report: Path,
    time_bins: int = 12, adjacent_each: int = 4,
    window_seconds: int = 180, sample_seconds: float = 2.0,
) -> dict:
    info, stored, labels, events, reference = _verify_day(video, annotations, report)
    if (sample_seconds not in (1.0, 2.0, 3.0)
            or abs(sample_seconds * info["fps"] -
                   round(sample_seconds * info["fps"])) > 1e-6):
        raise ValueError("Whole-second cadence must align with source FPS and 30s lookback")
    windows, audit = choose_controls(
        labels, events, fps=info["fps"], window_seconds=window_seconds,
        time_bins=time_bins, adjacent_each=adjacent_each,
    )
    pin = stored["in_memory_development_reference_pixel_sha256"]
    visibility = VisibilityQualityShadow.from_bgr(reference)
    reports = []
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise ValueError("Video decoder failed to open pinned camera research footage")
    try:
        for i, spec in enumerate(windows, 1):
            print(f"  annotated-normal bounded window {i}/{len(windows)}: "
                  f"{spec['control_stratum']}", flush=True)
            evaluated = _replay_window(
                cap, spec, info=info, labels=labels,
                pin=pin, visibility=visibility, sample_seconds=sample_seconds,
            )
            reports.append(_summarize_window(evaluated, sample_seconds))
    finally:
        cap.release()
    policies = {}
    for policy in POLICIES:
        policies[policy] = {
            "control_windows_with_any_candidate": sum(
                r["policies"][policy]["candidate_window_has_any_flag"] for r in reports
            ),
            "candidate_episode_starts_on_annotated_normal": sum(
                r["policies"][policy]["candidate_episode_starts"] for r in reports
            ),
            "candidate_active_samples_on_annotated_normal": sum(
                r["policies"][policy]["candidate_active_samples"] for r in reports
            ),
            "candidate_burden_is_conditional_on_selected_controls_only": True,
        }
    total_samples = sum(x["sampled_positions"] for x in reports)
    return {
        "status": STATUS,
        "production_qualified": False,
        "source_is_held_out": False,
        "normal_annotation_is_independent_health_truth": False,
        "source_reference_is_physical_camera_approved": False,
        "scene_raw_review_status_measured": False,
        "spatial_evidence_status_measured": False,
        "full_day_detector_replayed": False,
        "images_or_video_exported": False,
        "operational_incident_or_reference_mutated": False,
        "source_video_sha256": info["video_sha256"],
        "source_annotations_sha256": info["annotations_sha256"],
        "frozen_unapproved_reference_pixel_sha256": pin,
        "sample_rate_seconds": sample_seconds,
        "descriptive_exploratory_cutoff": CUTOFF,
        "sampling_audit": audit,
        "selected_window_count": len(reports),
        "sampled_numeric_positions": total_samples,
        "approx_annotated_normal_sample_hours": round(
            total_samples * sample_seconds / 3600, 5
        ),
        "policies": policies,
        "windows": reports,
        "limitations": [
            "Label-conditioned deterministic coverage sample, not statistically representative",
            "Recording progress strata are NOT verified day/night or wallclock periods",
            "Post/pre-event normal labels do not certify incident recovery or image usability",
            "Raw scene cue and spatial evidence UNMEASURED; no suppression permitted",
            "Camera reference is self-sourced and unapproved despite SHA-256 equality",
            "Conditional candidate episodes are NOT operator false-alert rates",
            "No independent camera, blinded quality ground truth, full-day validation, or calibration",
            "No candidate policy or existing raw scene warning is changed in production",
            "Only selected frames decoded; video files hashed against Phase3M",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for day in ("day3", "day4"):
        for field in ("video", "annotations", "report"):
            parser.add_argument(f"--{day}-{field}", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--time-bins", type=int, default=12)
    parser.add_argument("--adjacent-each", type=int, default=4)
    parser.add_argument("--window-seconds", type=int, default=180)
    parser.add_argument("--sample-seconds", type=float, default=2.0)
    parser.add_argument("--allow-unapproved-development-reference",
                        action="store_true")
    args = parser.parse_args()
    if not args.allow_unapproved_development_reference:
        parser.error("Explicit offline unapproved reference acknowledgement required")
    if args.sample_seconds not in (1.0, 2.0, 3.0):
        parser.error("Use exactly 1, 2 or 3 seconds to preserve frame-aligned 30s lookback")
    if args.out.suffix.lower() != ".json" or args.out.exists():
        parser.error("Output must be a new unused JSON path")
    results = {}
    for day in ("day3", "day4"):
        print(f"{day}: verifying pinned source and sampling normal strata", flush=True)
        results[day] = run_day(
            video=getattr(args, f"{day}_video"),
            annotations=getattr(args, f"{day}_annotations"),
            report=getattr(args, f"{day}_report"),
            time_bins=args.time_bins, adjacent_each=args.adjacent_each,
            window_seconds=args.window_seconds, sample_seconds=args.sample_seconds,
        )
    evidence = {
        "status": "PHASE3R_TWO_DAY_SYSTEMATIC_NORMAL_RESEARCH_ONLY",
        "development_reused": True,
        "held_out_validation": False,
        "production_qualified": False,
        "false_alert_rate_established": False,
        "media_exported": False,
        "operational_scene_warnings_modified": False,
        "automatic_reference_reenrollment_or_recovery": False,
        "days": results,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as f:
        json.dump(evidence, f, indent=2, sort_keys=True, allow_nan=False)
        f.write("\n")
    print(json.dumps({
        "status": evidence["status"],
        "normal_control_windows": {
            day: result["selected_window_count"] for day, result in results.items()
        },
        "report": str(args.out.resolve()),
        "production_qualified": False,
    }, indent=2))


if __name__ == "__main__":
    main()
