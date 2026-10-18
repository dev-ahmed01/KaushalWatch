#!/usr/bin/env python3
"""Phase 3S: repair MISSING pre-event controls without rerunning Phase 3R windows.

Selects new pre-event NORMAL-LABELED windows by deterministic label-only
selection. Read-only reuses Phase3M authenticated file digests (NOT an
approved camera reference), and audited Phase3R numeric report. Decodes
ONLY newly added pre-event intervals; produces numeric summaries.
Never changes original incidents, scene cues, source media, or references.

This is known development footage. Selecting the nearest eligible
control is NOT random sampling or independent adjudication.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

import cv2
import numpy as np

from app.services.camera_visibility_quality_shadow import VisibilityQualityShadow
from analyze_phase3s_normal_burden import analyze as audit_original
from run_phase3p_bounded_causal_quality import _verify_day, _replay_window
from run_phase3r_systematic_normal import (
    _make_normal_spec, _overlap, _summarize_window,
)
from analyze_phase3q_numeric_continuity import POLICIES


def ensure(condition: bool, explanation: str) -> None:
    if not condition:
        raise ValueError(explanation)


def select_missing_pre_event_controls(
    labels: np.ndarray, events: list[dict], existing: list[dict], *,
    fps: float, window_seconds: int = 180, take: int = 4,
) -> tuple[list[dict], dict]:
    ensure(isinstance(labels, np.ndarray) and labels.dtype == np.uint8 and labels.ndim == 1,
           "Require verified canonical integer frame labels")
    ensure(np.isfinite(fps) and fps > 0 and
           type(window_seconds) is int and 90 <= window_seconds <= 600 and
           type(take) is int and 0 <= take <= 12,
           "Invalid bounded pre-event sampling parameters")
    span = round(fps * window_seconds)
    total = len(labels)
    for original in existing:
        start, end = original.get("start_frame"), original.get("end_frame")
        ensure(type(start) is int and type(end) is int and
               1 <= start <= end <= total and
               np.all(labels[start-1:end] == 0), 
               "Existing Phase3R control frame interval is not all annotated normal")
    for i, left in enumerate(existing):
        for right in existing[i+1:]:
            ensure(not _overlap(left, right),
                   "Existing controls overlap and cannot be counted twice")

    seen = set()
    eligible = []
    for event in events:
        kind = event.get("kind")
        ensure(kind in (1, 2, 3), "Unexpected event annotation class")
        target = event.get("start_frame")
        ensure(type(target) is int, "Malformed event start")
        start, end = target-span, target-1
        if start < 1 or end > total or np.any(labels[start-1:end] != 0):
            continue
        key = (start, end)
        if key in seen:
            continue
        seen.add(key)
        eligible.append(_make_normal_spec(
            start, end, source="phase3s_pre_event_label_only",
            stratum=f"before_event_{target}",
        ))
    eligible.sort(key=lambda x: (x["start_frame"], x["end_frame"]))
    eligible_nonoverlap = [
        x for x in eligible if not any(_overlap(x, prev) for prev in existing)
    ]
    chosen: list[dict] = []
    picks = min(take, len(eligible_nonoverlap))
    for index in range(picks):
        # Predeclared quantile position; choose NEAREST non-overlapping
        # available eligible interval, rather than dropping the slot
        # when its exact target overlaps a fixed progress window.
        target_idx = min(
            len(eligible_nonoverlap)-1,
            int((index+0.5)*len(eligible_nonoverlap)/picks)
        )
        ordered_indices = sorted(
            range(len(eligible_nonoverlap)),
            key=lambda i: (abs(i-target_idx), i)
        )
        for i in ordered_indices:
            candidate = eligible_nonoverlap[i]
            if not any(_overlap(candidate, selected) for selected in chosen):
                chosen.append(candidate)
                break
    chosen.sort(key=lambda x: x["start_frame"])
    for selected in chosen:
        ensure(not any(_overlap(selected, w) for w in existing),
               "Pre-event control overlaps existing evidence")
        ensure(selected["end_frame"]-selected["start_frame"]+1 == span and
               np.all(labels[selected["start_frame"]-1:selected["end_frame"]] == 0),
               "Pre-event control includes abnormal labels")
    return chosen, {
        "source_selection": "deterministic_label_only_nearest_eligible_quantiles",
        "all_pre_event_label_eligible_candidates": len(eligible),
        "eligible_nonoverlapping_existing_phase3r_windows": len(eligible_nonoverlap),
        "planned_new_pre_event_windows": take,
        "selected_new_pre_event_windows": len(chosen),
        "unfilled_pre_event_targets": max(0, take-len(chosen)),
        "existing_windows_retained_without_reprocessing": len(existing),
        "all_controls_normal_label_only_not_independently_verified_healthy": True,
        "no_model_score_driven_window_selection": True,
    }


def evaluate_day(
    *, video: Path, annotations: Path, prior_phase3m: Path,
    original_phase3r: dict, day_key: str,
    sample_seconds: float = 2.0, take: int = 4,
    window_seconds: int = 180,
) -> dict:
    info, stored, labels, events, reference = _verify_day(
        video, annotations, prior_phase3m
    )
    previous = original_phase3r["days"][day_key]
    for file_key, current in (
        ("source_video_sha256", info["video_sha256"]),
        ("source_annotations_sha256", info["annotations_sha256"]),
        ("frozen_unapproved_reference_pixel_sha256",
         stored["in_memory_development_reference_pixel_sha256"]),
    ):
        ensure(previous.get(file_key) == current,
               "Phase3R numerical report source pin mismatch: "+file_key)
    ensure(previous["sample_rate_seconds"] == sample_seconds,
           "Phase3R original and Phase3S new sample cadence must agree")
    ensure(sample_seconds in (1.0, 2.0, 3.0) and
           abs(sample_seconds*info["fps"] - round(sample_seconds*info["fps"])) < 1e-6,
           "Require frame-aligned causal cadence")
    new_windows, sample_audit = select_missing_pre_event_controls(
        labels, events, previous["windows"], fps=info["fps"],
        window_seconds=window_seconds, take=take,
    )
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise ValueError("Pinned research video decoder unavailable")
    visibility = VisibilityQualityShadow.from_bgr(reference)
    new_reports = []
    try:
        for i, window in enumerate(new_windows, start=1):
            print(f"{day_key}: new pre-event normal control {i}/{len(new_windows)} "
                  f"{window['control_stratum']}", flush=True)
            replayed = _replay_window(
                cap, window, info=info, labels=labels,
                pin=stored["in_memory_development_reference_pixel_sha256"],
                visibility=visibility, sample_seconds=sample_seconds,
            )
            new_reports.append(_summarize_window(replayed, sample_seconds))
    finally:
        cap.release()
    original_reports = previous["windows"]
    combined = original_reports + new_reports
    comparison = {}
    for policy in POLICIES:
        original_episodes = sum(
            w["policies"][policy]["candidate_episode_starts"] for w in original_reports)
        added_episodes = sum(
            w["policies"][policy]["candidate_episode_starts"] for w in new_reports)
        comparison[policy] = {
            "existing_normal_labeled_candidate_episode_starts": original_episodes,
            "new_pre_event_normal_labeled_candidate_episode_starts": added_episodes,
            "combined_development_sample_candidate_episode_starts": original_episodes + added_episodes,
            "new_pre_event_windows_with_candidate": sum(
                w["policies"][policy]["candidate_window_has_any_flag"]
                for w in new_reports
            ),
            "selected_normal_sample_episode_count_not_false_alert_rate": True,
        }
    return {
        "status": "PHASE3S_BALANCED_PRE_EVENT_NUMERIC_RESEARCH_ONLY",
        "day": day_key,
        "source_video_sha256": info["video_sha256"],
        "source_annotations_sha256": info["annotations_sha256"],
        "prior_phase3r_selected_windows": len(original_reports),
        "prior_phase3r_original_numeric_windows_rereplayed": False,
        "new_pre_event_windows": len(new_reports),
        "sampling_audit": sample_audit,
        "policy_comparison": comparison,
        "new_pre_event_numeric_windows": new_reports,
        "production_qualified": False,
        "source_is_independent_holdout": False,
        "raw_scene_cues_or_spatial_evidence_measured": False,
        "physical_camera_reference_approved": False,
        "operator_recovery_or_scene_review_modified": False,
        "media_exported": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for day in ("day3", "day4"):
        for field in ("video", "annotations", "report"):
            parser.add_argument(f"--{day}-{field}", required=True, type=Path)
    parser.add_argument("--phase3r-report", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--pre-each", type=int, default=4)
    parser.add_argument("--window-seconds", type=int, default=180)
    parser.add_argument("--sample-seconds", type=float, default=2.0)
    parser.add_argument("--allow-unapproved-development-reference",
                        action="store_true")
    args = parser.parse_args()
    if not args.allow_unapproved_development_reference:
        parser.error("Explicit acknowledgment of unapproved Phase3M reference required")
    if args.out.suffix.lower() != ".json" or args.out.exists() or (
        args.out.resolve() == args.phase3r_report.resolve()
    ):
        parser.error("Output must be a NEW unused JSON path")
    source = json.loads(args.phase3r_report.read_text(encoding="utf-8"))
    original_triage = audit_original(source)
    ensure(original_triage["production_qualified"] is False,
           "Cannot use operational data in research sampling")
    days = {}
    for day in ("day3", "day4"):
        days[day] = evaluate_day(
            video=getattr(args, f"{day}_video"),
            annotations=getattr(args, f"{day}_annotations"),
            prior_phase3m=getattr(args, f"{day}_report"),
            original_phase3r=source, day_key=day,
            sample_seconds=args.sample_seconds, take=args.pre_each,
            window_seconds=args.window_seconds,
        )
    report = {
        "status": "PHASE3S_TWO_DAY_BALANCED_NORMAL_PRE_EVENT_RESEARCH_ONLY",
        "prior_phase3r_evidence_reused_without_duplicate_window_evaluation": True,
        "development_evidence_not_held_out": True,
        "camera_physical_reference_approved": False,
        "operational_scene_cues_modified": False,
        "incident_recovery_or_reference_rotation": False,
        "media_exported": False,
        "production_qualified": False,
        "days": days,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({
        "status": report["status"],
        "new_pre_windows": {
            day: result["new_pre_event_windows"] for day, result in days.items()
        },
        "output": str(args.out.resolve()),
        "production_qualified": False,
    }, indent=2))


if __name__ == "__main__":
    main()
