#!/usr/bin/env python3
"""Phase 3O: annotation-aligned, development-only quality transitions.

Consume Phase 3N NUMERIC JSON only. No video/frames/images, no detector replay,
no threshold fitting, no operational alert decisions. The reference remains
unapproved. Each pre-event comparison requires a normal-labeled anchor, but
normal-labeled does NOT mean independently verified camera health.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import statistics

STAGES = (
    "before_start", "onset", "after_onset_30", "event_end",
    "after_end_30", "after_end_120",
)
KINDS = ("defocused", "moved")
METRICS = ("relative_sharpness", "relative_edge_fraction", "relative_contrast")
HYPOTHESES = frozenset((
    "SHARPNESS_LOSS_COMPATIBLE", "REFERENCE_TEXTURE_INSUFFICIENT",
    "ILLUMINATION_CONFOUNDED", "NO_SHARPNESS_LOSS_SIGNAL",
))
# Diagnostic cutoffs selected for transparent sensitivity analysis on
# previously inspected development data. They are NOT trained, calibrated,
# pre-registered, deployed or candidate production thresholds.
EXPLORATORY_SHARPNESS_RATIOS = (0.35, 0.50, 0.65)


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def _finite_nonnegative(value: object) -> bool:
    return (type(value) in (int, float) and
            math.isfinite(value) and value >= 0)


def _median(values: list[float]) -> float | None:
    return round(statistics.median(values), 5) if values else None


def _validate_and_group(day: dict, name: str) -> dict:
    _require(isinstance(day, dict), name + ": expected object")
    _require(day.get("status") == "PHASE3N_TARGETED_UNAPPROVED_REFERENCE_DEVELOPMENT_ONLY",
             name + ": wrong Phase3N source status")
    for flag, expected in (
        ("production_qualified", False),
        ("physical_reference_verified", False),
        ("source_is_held_out", False),
        ("frames_images_or_crops_exported", False),
        ("same_unnapproved_in_video_reference_as_phase3m", True),
        ("complete_video_replayed", False),
    ):
        _require(day.get(flag) is expected, name + ": source assurance mismatch: " + flag)
    samples = day.get("sampled_positions")
    _require(isinstance(samples, list) and len(samples) > 0,
             name + ": empty or invalid positions")
    _require(type(day.get("sampled_target_frames")) is int and
             day["sampled_target_frames"] == len(samples),
             name + ": sampled-frame count mismatch")
    events: dict[tuple[str, int], dict] = defaultdict(dict)
    for item in samples:
        _require(isinstance(item, dict), name + ": malformed sample")
        kind, stage, start = (
            item.get("target_event_class"), item.get("stage"),
            item.get("target_event_start_frame"),
        )
        _require(kind in KINDS and stage in STAGES and
                 type(start) is int and start > 0,
                 name + ": malformed event identifier")
        _require(type(item.get("sample_frame")) is int and
                 item["sample_frame"] > 0,
                 name + ": invalid frame number")
        _require(type(item.get("target_event_end_frame")) is int and
                 item["target_event_end_frame"] >= start,
                 name + ": invalid event end")
        _require(item.get("actual_annotation_class_at_sample") in
                 ("normal", "covered", "defocused", "moved"),
                 name + ": unknown annotation")
        _require(item.get("quality_hypothesis") in HYPOTHESES,
                 name + ": unknown quality hypothesis")
        for metric in METRICS:
            _require(_finite_nonnegative(item.get(metric)),
                     name + ": missing or invalid " + metric)
        for key in ("baseline_event_any_review", "baseline_event_fresh_review"):
            _require(type(item.get(key)) is bool,
                     name + ": missing baseline field " + key)
        _require(not item["baseline_event_fresh_review"] or
                 item["baseline_event_any_review"],
                 name + ": fresh review must also count as any review")
        key = (kind, start)
        _require(stage not in events[key],
                 name + ": duplicate event stage")
        events[key][stage] = item
    for key, stages in events.items():
        _require(set(stages) == set(STAGES),
                 name + ": incomplete six-stage event")
        any_status = {s["baseline_event_any_review"] for s in stages.values()}
        fresh_status = {s["baseline_event_fresh_review"] for s in stages.values()}
        ends = {s["target_event_end_frame"] for s in stages.values()}
        _require(len(any_status) == len(fresh_status) == len(ends) == 1,
                 name + ": inconsistent event metadata")
        _require(stages["onset"]["actual_annotation_class_at_sample"] == key[0] and
                 stages["event_end"]["actual_annotation_class_at_sample"] == key[0],
                 name + ": onset/end labels do not match event")
    return events


def _one_pair(day: str, key: tuple[str, int], samples: dict) -> dict:
    anchor = samples["before_start"]
    anchor_normal = anchor["actual_annotation_class_at_sample"] == "normal"
    ratios = {}
    for stage in STAGES[1:]:
        current = samples[stage]
        valid_label = current["actual_annotation_class_at_sample"] == (
            key[0] if stage in ("onset", "after_onset_30", "event_end") else "normal"
        )
        result = {}
        for metric in METRICS:
            before = anchor[metric]
            result[metric] = (
                round(current[metric] / before, 6)
                if anchor_normal and valid_label and before > 1e-6
                else None
            )
        ratios[stage] = result
    return {
        "day": day,
        "event_class": key[0],
        "event_start_frame": key[1],
        "baseline_any_scene_review": samples["onset"]["baseline_event_any_review"],
        "baseline_fresh_scene_review": samples["onset"]["baseline_event_fresh_review"],
        "anchor_annotation_normal": anchor_normal,
        "anchor_quality_hypothesis": anchor["quality_hypothesis"],
        "quality_hypothesis_by_stage": {
            stage: samples[stage]["quality_hypothesis"] for stage in STAGES
        },
        "actual_annotation_by_stage": {
            stage: samples[stage]["actual_annotation_class_at_sample"]
            for stage in STAGES
        },
        "within_event_ratio_to_before_start": ratios,
    }


def _summarize(pairs: list[dict]) -> dict:
    result = {}
    for kind in KINDS:
        selected = [p for p in pairs if p["event_class"] == kind]
        out = {
            "sampled_events": len(selected),
            "baseline_any_scene_review_events": sum(
                p["baseline_any_scene_review"] for p in selected
            ),
            "baseline_fresh_scene_review_events": sum(
                p["baseline_fresh_scene_review"] for p in selected
            ),
            "anchor_illumination_confound_events": sum(
                p["anchor_quality_hypothesis"] == "ILLUMINATION_CONFOUNDED"
                for p in selected
            ),
            "hypothesis_at_30s": dict(Counter(
                p["quality_hypothesis_by_stage"]["after_onset_30"]
                for p in selected
            )),
            "stage_ratios": {},
        }
        for stage in STAGES[1:]:
            scores = {
                metric: [
                    p["within_event_ratio_to_before_start"][stage][metric]
                    for p in selected
                    if p["within_event_ratio_to_before_start"][stage][metric]
                    is not None
                ]
                for metric in METRICS
            }
            sharp = scores["relative_sharpness"]
            out["stage_ratios"][stage] = {
                "valid_paired_events": len(sharp),
                "abstained_events": len(selected) - len(sharp),
                "median_sharpness_ratio": _median(sharp),
                "median_edge_fraction_ratio": _median(scores["relative_edge_fraction"]),
                "median_contrast_ratio": _median(scores["relative_contrast"]),
                "exploratory_sharpness_decline_counts": {
                    str(cutoff): sum(x <= cutoff for x in sharp)
                    for cutoff in EXPLORATORY_SHARPNESS_RATIOS
                },
                "edge_half_or_lower_count": sum(
                    x <= 0.5 for x in scores["relative_edge_fraction"]
                ),
            }
        result[kind] = out
    return result


def analyze(report: dict) -> dict:
    _require(isinstance(report, dict) and
             report.get("status") ==
             "PHASE3N_TWO_DAY_TARGETED_VISIBILITY_NOT_HELD_OUT",
             "Require a completed Phase3N two-day numeric development report")
    for flag in ("production_qualified", "media_exported",
                 "automatic_recovery_or_reference_reset", "full_day_repeated"):
        _require(report.get(flag) is False,
                 "Phase3N source must explicitly block " + flag)
    days = report.get("days")
    _require(isinstance(days, dict) and set(days) == {"day3", "day4"},
             "Expected the complete Day3 + Day4 targeted report")
    day_results = {}
    all_pairs = []
    for name in ("day3", "day4"):
        events = _validate_and_group(days[name], name)
        pairs = [
            _one_pair(name, key, stages)
            for key, stages in sorted(events.items(), key=lambda t: t[0][1])
        ]
        all_pairs.extend(pairs)
        day_results[name] = {
            "grouped_events": len(events),
            "summary": _summarize(pairs),
        }
    return {
        "status": "PHASE3O_PAIRED_TRANSITION_DESCRIPTIVE_RESEARCH_ONLY",
        "source_status": report["status"],
        "development_data_previously_inspected": True,
        "thresholds_calibrated": False,
        "thresholds_preregistered": False,
        "held_out_evaluation": False,
        "independent_ground_truth": False,
        "reference_approved": False,
        "production_qualified": False,
        "production_integration": False,
        "detector_or_scene_reviews_modified": False,
        "automatic_recovery_or_reference_reset": False,
        "media_exported": False,
        "exploratory_cutoffs_paired_sharpness": list(EXPLORATORY_SHARPNESS_RATIOS),
        "method": (
            "For each annotation-defined event, divide the existing "
            "fixed-reference-relative metric at a stage by the metric "
            "30 seconds before event start. Same fixed reference cancels "
            "algebraically. Require normal annotation at anchor and "
            "matching event/normal annotation at the compared stage; "
            "otherwise abstain. This is NOT a real-time detector because "
            "event starts come from retrospective annotations."
        ),
        "days": day_results,
        "pooled": _summarize(all_pairs),
        "event_ratios_numeric_only": all_pairs,
        "limitations": [
            "All observations are prior inspected development data, NOT independent hold-out",
            "Normal-annotated pre-event anchors are not authenticated healthy footage",
            "Onset and stage sampling use retrospective event labels, unavailable in operation",
            "Sharpness may shift with motion, scene changes, compression, light or obstruction",
            "Moved controls are not representative of all normal camera footage",
            "No full-time false-positive rate, precision, recall, onset latency or usability proof",
            "Paired ratios/diagnostic cutoffs are descriptive, NOT trained production thresholds",
            "No image/video/crop export, live notifications, reference enrollment, recovery or sanctions",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    if args.out.suffix.lower() != ".json" or args.out.exists():
        parser.error("Choose a new unused .json output path")
    if args.out.resolve() == args.input.resolve():
        parser.error("Never overwrite the Phase3N original")
    report = json.loads(args.input.read_text(encoding="utf-8"))
    result = analyze(report)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "events": {k: v["sampled_events"]
                   for k, v in result["pooled"].items()},
        "report": str(args.out.resolve()),
        "production_qualified": False,
    }, indent=2))


if __name__ == "__main__":
    main()
