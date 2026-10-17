#!/usr/bin/env python3
"""Phase 3P: bounded local causal image-quality replay, numeric evidence only.

Uses verified Phase3M source videos, annotations, and unapproved reference.
Event annotations determine OFFLINE window selection and post-hoc grouping,
but NEVER enter the monitor.observe() call or select an in-window anchor.
There are deliberately no scene-review/spatial statuses available in the
prior summary: both are explicitly NOT_MEASURED, never fabricated as healthy.
No full-day detector replay, media export, recovery action or deployment.
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
from app.services.camera_causal_temporal_quality_shadow import CausalTemporalQualityShadow  # noqa: E402
from app.services.camera_visibility_quality_shadow import VisibilityQualityShadow  # noqa: E402
from run_phase3m_dual_day_research import (  # noqa: E402
    _read_source, _choose_reference_index, _frame_in_memory, _memory_sha, _write_json,
)
from run_phase3n_targeted_visibility import (  # noqa: E402
    _labels_and_events, _read_exact_frame,
)

KINDS = {0: "normal", 1: "covered", 2: "defocused", 3: "moved"}
WINDOW_BEFORE_SECONDS = 60
WINDOW_AFTER_SECONDS = 120


def _verify_day(video: Path, annotations: Path, report_path: Path) -> tuple[dict, dict, np.ndarray, list[dict], np.ndarray]:
    stored = json.loads(Path(report_path).read_text(encoding="utf-8"))
    if (stored.get("status") !=
            "FULL_DEVELOPMENT_CAUSE_REPLAY_UNAPPROVED_REFERENCE_NOT_HELD_OUT"
            or stored.get("production_qualified") is not False
            or stored.get("production_integration") is not False
            or stored.get("evaluated_frames") != stored.get("total_frames")):
        raise ValueError("Require completed unqualified Phase3M FULL source report")
    info = _read_source(video, annotations)
    for report_key, info_key in (
        ("video_sha256", "video_sha256"),
        ("annotations_sha256", "annotations_sha256"),
        ("total_frames", "frames"),
    ):
        if stored.get(report_key) != info.get(info_key):
            raise ValueError("Pinned Phase3M source metadata disagrees: " + report_key)
    reference_frame, _ = _choose_reference_index(
        annotations, fps=info["fps"], frames=info["frames"],
    )
    if stored.get("in_memory_development_reference_source_frame") != reference_frame:
        raise ValueError("Phase3M frozen unapproved reference frame mismatch")
    reference = _frame_in_memory(video, frame_number=reference_frame, expected=info)
    if _memory_sha(reference) != stored.get("in_memory_development_reference_pixel_sha256"):
        raise ValueError("Phase3M reference pixel digest mismatch")
    labels, events = _labels_and_events(annotations, info["frames"])
    counts = Counter(KINDS[x["kind"]] for x in events)
    for kind in ("covered", "defocused", "moved"):
        if counts[kind] != stored.get("annotated_event_counts", {}).get(kind, 0):
            raise ValueError("Annotated event counts disagree with Phase3M")
    return info, stored, labels, events, reference


def _sample_events(events: list[dict], *, kind: int, count: int) -> list[dict]:
    """Systematically select evenly spaced events independent of model output."""
    selected = [e for e in events if e["kind"] == kind]
    if not selected:
        return []
    # Floor of midpoint of each quantile, preserving chronology and uniqueness.
    take = min(len(selected), count)
    indices = sorted(set(min(len(selected)-1, int((i + .5)*len(selected)/take))
                         for i in range(take)))
    return [selected[i] for i in indices]


def _window_specs(
    labels: np.ndarray, events: list[dict], *, fps: float,
    count_per_kind: int = 6, normal_control_windows: int = 4,
) -> tuple[list[dict], list[dict]]:
    total = len(labels)
    before = round(WINDOW_BEFORE_SECONDS*fps)
    after = round(WINDOW_AFTER_SECONDS*fps)
    specs = []
    for kind in (2, 3):
        for e in _sample_events(events, kind=kind, count=count_per_kind):
            start = max(1, e["start_frame"] - before)
            end = min(total, e["start_frame"] + after)
            specs.append({
                "kind": KINDS[kind], "start_frame": start, "end_frame": end,
                "target_event_start_frame": e["start_frame"],
                "target_event_end_frame": e["end_frame"],
                "selection": "predeclared_event_quantiles",
            })
    skipped = []
    for i in range(1, normal_control_windows+1):
        center = int(total*i/(normal_control_windows+1))
        start = max(1, center-before)
        end = min(total, center+after)
        # Labels only govern offline control WINDOW selection; NEVER an anchor
        # or an online quality decision. We report skipped invalid windows.
        if end-start+1 < before+after or not np.all(labels[start-1:end] == 0):
            skipped.append({"center_frame": center,
                            "reason": "predeclared_control_not_all_annotated_normal"})
            continue
        specs.append({
            "kind": "normal_control", "start_frame": start,
            "end_frame": end, "target_event_start_frame": None,
            "target_event_end_frame": None,
            "selection": "predeclared_quartile_control",
        })
    return specs, skipped


def _replay_window(cap, spec: dict, *, info: dict, labels: np.ndarray, pin: str,
                   visibility: VisibilityQualityShadow,
                   sample_seconds: float) -> dict:
    observer = CausalTemporalQualityShadow(
        reference_pixel_sha256=pin,
        lookback_seconds=30.0,
        tolerance_seconds=max(1.0, sample_seconds * 0.6),
        max_gap_seconds=sample_seconds * 1.6,
    )
    step_frames = max(1, round(sample_seconds*info["fps"]))
    results = []
    for n in range(spec["start_frame"], spec["end_frame"]+1, step_frames):
        item = _read_exact_frame(cap, n, (info["height"], info["width"]))
        features = visibility.inspect(item)
        state = observer.observe(
            time_s=(n-1)/info["fps"],
            reference_pixel_sha256=pin,
            features=features,
            spatial_evidence_status="NOT_MEASURED",
            raw_scene_review=None,
        )
        # The annotation is read strictly AFTER observe, for offline scoring;
        # it is NEVER a causal input or an approved healthy anchor.
        actual_annotation = KINDS[int(labels[n-1])]
        offset = None
        if spec["target_event_start_frame"] is not None:
            offset = round((n-spec["target_event_start_frame"])/info["fps"], 3)
        results.append({
            "sample_frame": n,
            "annotation_class_for_posthoc_evaluation_only": actual_annotation,
            "offset_from_target_start_seconds_for_posthoc_analysis": offset,
            "sharpness_relative_to_unchanged_fixed_reference": features["relative_sharpness"],
            "quality_hypothesis": features["quality_hypothesis"],
            "comparison_state": state["comparison_state"],
            "paired_sharpness_ratio": (
                state["paired_numeric_ratios"]["sharpness"]
                if state["paired_numeric_ratios"] is not None else None
            ),
            "paired_edge_fraction_ratio": (
                state["paired_numeric_ratios"]["edge_fraction"]
                if state["paired_numeric_ratios"] is not None else None
            ),
            "confounds": state["confounds"],
            "exploratory_drop_0_5": state["exploratory_sharpness_ratio_at_most_half"],
        })
    return {
        **spec,
        "sample_seconds_requested": sample_seconds,
        "samples": results,
        "observer_summary": observer.summary(),
        "frames_or_media_exported": False,
    }


def run_day(*, video: Path, annotations: Path, report: Path,
            event_count: int, normal_controls: int, sample_seconds: float) -> dict:
    info, stored, labels, events, reference = _verify_day(video, annotations, report)
    specs, skipped = _window_specs(
        labels, events, fps=info["fps"],
        count_per_kind=event_count, normal_control_windows=normal_controls,
    )
    pin = stored["in_memory_development_reference_pixel_sha256"]
    visibility = VisibilityQualityShadow.from_bgr(reference)
    windows = []
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise ValueError("Could not open source video decoder")
    try:
        for index, spec in enumerate(specs, 1):
            print(f"  bounded window {index}/{len(specs)}: {spec['kind']}", flush=True)
            windows.append(_replay_window(
                cap, spec, info=info, labels=labels, pin=pin,
                visibility=visibility, sample_seconds=sample_seconds,
            ))
    finally:
        cap.release()
    summary = {}
    for kind in ("defocused", "moved", "normal_control"):
        selected = [w for w in windows if w["kind"] == kind]
        paired = [s for w in selected for s in w["samples"]
                  if s["paired_sharpness_ratio"] is not None]
        triggered = [s for s in paired if s["exploratory_drop_0_5"]]
        in_target = [s for w in selected for s in w["samples"]
                     if w["target_event_start_frame"] is not None
                     and s["annotation_class_for_posthoc_evaluation_only"] == kind
                     and s["offset_from_target_start_seconds_for_posthoc_analysis"] is not None
                     and 0 <= s["offset_from_target_start_seconds_for_posthoc_analysis"] <= WINDOW_AFTER_SECONDS]
        summary[kind] = {
            "selected_windows": len(selected),
            "annotated_target_samples_in_window": len(in_target),
            "exploratory_drop_samples_inside_target": sum(s["exploratory_drop_0_5"] is True for s in in_target),
            "sampled_observations": sum(len(w["samples"]) for w in selected),
            "paired_numeric_observations": len(paired),
            "exploratory_sharpness_drop_samples": len(triggered),
            "counts_are_not_precision_recall_or_false_alarm_rates": True,
        }
    return {
        "status": "PHASE3P_BOUNDED_CAUSAL_DEVELOPMENT_REPLAY_NOT_HELD_OUT",
        "production_qualified": False,
        "full_day_detector_replayed": False,
        "source_is_held_out": False,
        "reference_is_approved": False,
        "scene_raw_review_status_measured": False,
        "spatial_evidence_status_measured": False,
        "automatic_reference_reset_or_recovery": False,
        "video_or_images_exported": False,
        "source_video_sha256": info["video_sha256"],
        "source_annotations_sha256": info["annotations_sha256"],
        "sample_rate_seconds": sample_seconds,
        "selection_window_before_seconds": WINDOW_BEFORE_SECONDS,
        "selection_window_after_seconds": WINDOW_AFTER_SECONDS,
        "skipped_annotated_normal_controls": skipped,
        "summary": summary,
        "windows": windows,
        "limitations": [
            "Development windows selected using annotations; offline only",
            "Within each window observer sees ONLY previous numeric features, no event labels",
            "Normal-annotated control footage is not independently proven healthy",
            "Frame-level raw scene-review and spatial evidence unavailable: NOT_MEASURED, never falsely healthy",
            "AVI seeking is decoder-dependent; local codec accuracy not independently reviewed",
            "No full-day normal-period burden, recall, certified latency, or incident recovery claims",
            "Exploratory ratio 0.5 not preregistered, calibrated, or production admissible",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("day3", "day4"):
        parser.add_argument("--"+name+"-video", required=True, type=Path)
        parser.add_argument("--"+name+"-annotations", required=True, type=Path)
        parser.add_argument("--"+name+"-report", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--events-per-kind", type=int, default=6)
    parser.add_argument("--normal-controls", type=int, default=4)
    parser.add_argument("--sample-seconds", type=float, default=2.0)
    parser.add_argument("--allow-unapproved-development-reference", action="store_true")
    args = parser.parse_args()
    if not args.allow_unapproved_development_reference:
        parser.error("Explicit unapproved development-only reference acknowledgement required")
    if (args.events_per_kind < 1 or args.events_per_kind > 24 or
            args.normal_controls < 0 or args.normal_controls > 12 or
            not np.isfinite(args.sample_seconds) or
            args.sample_seconds < 1 or args.sample_seconds > 4):
        parser.error("Bounded events <=24, normal controls <=12, sample interval 1-4s required")
    if args.out.suffix.lower() != ".json" or args.out.exists():
        parser.error("Use a new unused .json report path")
    days = {}
    for name in ("day3", "day4"):
        print(name + ": selected bounded quality windows", flush=True)
        days[name] = run_day(
            video=getattr(args, name+"_video"),
            annotations=getattr(args, name+"_annotations"),
            report=getattr(args, name+"_report"),
            event_count=args.events_per_kind,
            normal_controls=args.normal_controls,
            sample_seconds=args.sample_seconds,
        )
    result = {
        "status": "PHASE3P_BOUNDED_TWO_DAY_CAUSAL_NUMERIC_EVIDENCE_ONLY",
        "production_qualified": False,
        "all_video_frames_replayed": False,
        "media_exported": False,
        "operational_alerts_modified": False,
        "automatic_reference_reset_or_recovery": False,
        "days": days,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    _write_json(args.out, result)
    print(json.dumps({
        "status": result["status"],
        "window_counts_by_day": {k: len(v["windows"]) for k, v in days.items()},
        "report": str(args.out.resolve()),
        "production_qualified": False,
    }, indent=2))


if __name__ == "__main__":
    main()
