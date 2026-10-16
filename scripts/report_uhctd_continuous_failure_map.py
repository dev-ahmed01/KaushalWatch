#!/usr/bin/env python3
"""Rank continuous UHCTD shadow failure periods from numerical outputs only.

Requires the extended evaluator's per-hour normal-review counts and normal
episode CSV. Never reads videos, re-enrolls camera reference, changes thresholds
or establishes held-out qualification.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path


def nonnegative(value, label: str) -> float:
    try:
        number = float(value)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Bad {label}") from exc
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"Bad {label}")
    return number


def summarize_one(directory: Path, top: int = 5) -> dict:
    directory = directory.resolve()
    path = directory / "continuous_shadow_summary.json"
    episodes_path = directory / "continuous_shadow_normal_review_episodes.csv"
    if not path.is_file() or not episodes_path.is_file():
        raise ValueError(f"Missing extended continuous report in {directory}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if (raw.get("status") != "COMPLETE_CONTINUOUS_DEVELOPMENT_NOT_HELD_OUT"
            or raw.get("qualified") is not False
            or raw.get("production_integration") is not False):
        raise ValueError("Complete, explicitly nonqualified development report required")
    hours = raw.get("normal_review_hours")
    if not isinstance(hours, list) or not hours:
        raise ValueError("Missing per-hour instrumentation; rerun updated evaluator")

    parsed_hours = []
    seen_hours = set()
    for h in hours:
        hour = int(h["hour_from_recording_start"])
        normal = nonnegative(h["normal_samples"], "normal_samples")
        spatial = nonnegative(h["spatial_review_samples"], "spatial_review_samples")
        fallback = nonnegative(h["fusion_from_global_fallback_samples"], "global_fallback")
        fusion = nonnegative(h["fusion_review_samples"], "fusion_review_samples")
        unknown = nonnegative(h["unknown_low_texture_samples"], "unknown")
        quality = nonnegative(h["global_quality_limited_samples"], "quality")
        new = nonnegative(h["new_fusion_review_episodes"], "new_episodes")
        spatial_source = nonnegative(h["fusion_from_spatial_samples"], "spatial_source")
        if (hour < 0 or hour in seen_hours or normal <= 0 or fusion > normal
                or abs(spatial_source + fallback - fusion) > 0.01
                or spatial_source > spatial or unknown > normal or quality > normal):
            raise ValueError("Inconsistent per-hour numeric results")
        seen_hours.add(hour)
        parsed_hours.append({
            "hour_from_start": hour,
            "normal_samples": int(normal),
            "fusion_review_samples": int(fusion),
            "fusion_normal_fraction": round(fusion / normal, 6),
            "fusion_spatial_samples": int(spatial_source),
            "fusion_global_fallback_samples": int(fallback),
            "unknown_low_texture_samples": int(unknown),
            "global_quality_limited_samples": int(quality),
            "new_review_episodes": int(new),
        })

    expected = raw["methods"]["fusion"]["normal_review_samples"]
    if sum(h["fusion_review_samples"] for h in parsed_hours) != expected:
        raise ValueError("Hour bins do not reconcile to published continuous summary")
    rows = []
    with episodes_path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {
            "start_frame", "end_frame", "samples", "spatial_cue_samples",
            "global_fallback_samples", "start_seconds", "end_seconds",
            "already_alerted_before_normal_span",
        }
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("Episode CSV is missing required fields")
        for row in reader:
            n = int(nonnegative(row["samples"], "samples"))
            s = int(nonnegative(row["spatial_cue_samples"], "spatial_cue_samples"))
            g = int(nonnegative(row["global_fallback_samples"], "global_fallback_samples"))
            start = nonnegative(row["start_seconds"], "start_seconds")
            end = nonnegative(row["end_seconds"], "end_seconds")
            if n < 1 or s + g != n or end < start:
                raise ValueError("Episode does not reconcile to review-sample sources")
            previous = row["already_alerted_before_normal_span"]
            if previous not in ("True", "False"):
                raise ValueError("Invalid episode carried-over flag")
            rows.append({
                "start_minutes_from_start": round(start / 60, 3),
                "end_minutes_from_start": round(end / 60, 3),
                "sampled_review_seconds": round(
                    n * nonnegative(raw["effective_sample_seconds"], "cadence"), 3
                ),
                "samples": n,
                "spatial_source_samples": s,
                "global_fallback_source_samples": g,
                "carried_from_prior_label": previous == "True",
            })
    if sum(e["samples"] for e in rows) != expected:
        raise ValueError("Normal episodes do not reconcile to published summary")

    return {
        "status": "NUMERIC_CONTINUOUS_DEV_FAILURE_MAP_NOT_HELD_OUT",
        "normal_review_fraction": raw["methods"]["fusion"]["normal_review_fraction"],
        "new_review_episodes_per_normal_hour":
            raw["methods"]["fusion"]["new_normal_review_episodes_per_normal_hour"],
        "annotation_normal_review_samples": expected,
        "fusion_spatial_source_samples":
            sum(h["fusion_spatial_samples"] for h in parsed_hours),
        "fusion_global_fallback_samples":
            sum(h["fusion_global_fallback_samples"] for h in parsed_hours),
        "normal_review_spans": len(rows),
        "carried_from_prior_label_spans":
            sum(e["carried_from_prior_label"] for e in rows),
        "top_hours_by_review_sample_volume": sorted(
            parsed_hours, key=lambda x: (-x["fusion_review_samples"], x["hour_from_start"])
        )[:top],
        "top_hours_by_new_review_episodes": sorted(
            parsed_hours, key=lambda x: (-x["new_review_episodes"], x["hour_from_start"])
        )[:top],
        "longest_normal_review_spans": sorted(
            rows, key=lambda x: -x["samples"]
        )[:top],
        "interpretation": (
            "No labeled camera-tamper event is not proof that visual evidence "
            "was usable. Episode times are offsets from video start, not "
            "local civil clock time. No underlying images inspected."
        ),
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--day3", type=Path, required=True, help="Extended day3 output directory")
    p.add_argument("--day4", type=Path, required=True, help="Extended day4 output directory")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--top", type=int, default=5)
    args = p.parse_args()
    if not 1 <= args.top <= 20:
        p.error("Top must be between 1 and 20")
    result = {
        "status": "CONTINUOUS_SHADOW_FAILURE_MAP_DEVELOPMENT_ONLY",
        "qualified": False,
        "day3": summarize_one(args.day3, top=args.top),
        "day4": summarize_one(args.day4, top=args.top),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    for day in ("day3", "day4"):
        d = result[day]
        print(f"\n=== {day.upper()} ===")
        print("Normal review:", d["normal_review_fraction"],
              "| alerts / normal hour:", d["new_review_episodes_per_normal_hour"])
        print("Review sample origins (spatial/global fallback):",
              d["fusion_spatial_source_samples"], "/",
              d["fusion_global_fallback_samples"])
        print("Top hours by normal review volume:",
              json.dumps(d["top_hours_by_review_sample_volume"]))
        print("Top hours by new review episodes:",
              json.dumps(d["top_hours_by_new_review_episodes"]))
        print("Longest normal review spans:",
              json.dumps(d["longest_normal_review_spans"]))
    print("\nNumeric failure map:", args.out.resolve())


if __name__ == "__main__":
    main()
