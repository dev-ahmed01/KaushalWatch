#!/usr/bin/env python3
"""Classify review episodes adjacent to annotated camera events, without video.

Consumes only existing continuous-shadow JSON and CSV numerical outputs.
This is *not* independent validation, causal attribution, camera recovery
verification, or proof of tampering. No detector thresholds or references
are changed.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path


def _num(value, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid {label}") from exc
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"Invalid {label}")
    return number


def _bool(value: str, label: str) -> bool:
    if value not in ("True", "False"):
        raise ValueError(f"Invalid {label}; expected True or False")
    return value == "True"


def _read_csv(path: Path, required: set[str]) -> list[dict]:
    if not path.is_file():
        raise ValueError(f"Missing required numerical CSV: {path}")
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"Missing numerical CSV columns: {path.name}")
        return list(reader)


def classify(directory: Path, *, nearby_seconds: float = 60.0,
             top: int = 8) -> dict:
    """Cross-reference temporal proximity; do not assign cause to alerts."""
    if not math.isfinite(nearby_seconds) or nearby_seconds < 0:
        raise ValueError("nearby_seconds must be finite and nonnegative")
    if not 1 <= top <= 100:
        raise ValueError("top must be between 1 and 100")
    directory = directory.resolve()
    summary_path = directory / "continuous_shadow_summary.json"
    if not summary_path.is_file():
        raise ValueError(f"Missing continuous summary: {summary_path}")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if (summary.get("status") != "COMPLETE_CONTINUOUS_DEVELOPMENT_NOT_HELD_OUT"
            or summary.get("qualified") is not False
            or summary.get("production_integration") is not False):
        raise ValueError("Only complete unqualified development reports accepted")
    fps = _num(summary.get("fps"), "FPS")
    interval = _num(summary.get("effective_sample_seconds"), "sample interval")
    if fps == 0 or interval == 0:
        raise ValueError("Video FPS and sample interval must be positive")
    expected = int(summary["methods"]["fusion"]["normal_review_samples"])

    event_rows = _read_csv(
        directory / "continuous_shadow_events.csv",
        {"class", "start_frame", "end_frame", "method"},
    )
    events = []
    for row in event_rows:
        if row["method"] != "fusion":
            continue
        if row["class"] not in ("covered", "defocused", "moved"):
            raise ValueError("Unexpected annotated event class")
        start = int(_num(row["start_frame"], "event start"))
        end = int(_num(row["end_frame"], "event end"))
        if start < 1 or end < start:
            raise ValueError("Bad event interval")
        events.append({"class": row["class"], "start": start, "end": end})
    events.sort(key=lambda item: item["start"])
    for earlier, later in zip(events, events[1:]):
        if earlier["end"] >= later["start"]:
            raise ValueError("Overlapping annotated event intervals")

    episode_rows = _read_csv(
        directory / "continuous_shadow_normal_review_episodes.csv",
        {"start_frame", "end_frame", "samples", "spatial_cue_samples",
         "global_fallback_samples", "already_alerted_before_normal_span"},
    )
    episodes = []
    prev_start = 0
    for row in episode_rows:
        start = int(_num(row["start_frame"], "episode start"))
        end = int(_num(row["end_frame"], "episode end"))
        count = int(_num(row["samples"], "episode samples"))
        spatial = int(_num(row["spatial_cue_samples"], "spatial samples"))
        global_count = int(_num(row["global_fallback_samples"], "global samples"))
        carried = _bool(
            row["already_alerted_before_normal_span"], "carried flag"
        )
        if (start < 1 or end < start or start <= prev_start or count < 1
                or spatial + global_count != count):
            raise ValueError("Inconsistent normal review episode")
        prev_start = start
        prior = next((ev for ev in reversed(events) if ev["end"] < start), None)
        gap_seconds = (start - prior["end"]) / fps if prior else None
        within_window = (
            gap_seconds is not None and gap_seconds <= nearby_seconds
        )
        episodes.append({
            "start_frame": start,
            "end_frame": end,
            "start_minutes_from_recording_start": round((start - 1) / fps / 60, 3),
            "sampled_review_seconds": round(count * interval, 3),
            "normal_review_samples": count,
            "spatial_samples": spatial,
            "global_fallback_samples": global_count,
            "was_already_alerted_at_normal_span_start": carried,
            "nearest_prior_annotated_event_class": (
                prior["class"] if prior else None
            ),
            "seconds_since_prior_event_end": (
                round(gap_seconds, 3) if gap_seconds is not None else None
            ),
            "start_near_prior_event": within_window,
        })
    if sum(item["normal_review_samples"] for item in episodes) != expected:
        raise ValueError("Normal review episode totals fail to reconcile")
    carried = [e for e in episodes if e["was_already_alerted_at_normal_span_start"]]
    adjacent = [e for e in episodes if e["start_near_prior_event"]]
    carried_count = sum(e["normal_review_samples"] for e in carried)
    adjacent_count = sum(e["normal_review_samples"] for e in adjacent)
    return {
        "status": "COMPLETE_DEVELOPMENT_EVENT_ADJACENCY_NOT_CAUSAL_EVIDENCE",
        "qualified": False,
        "source_directory": str(directory),
        "nearby_seconds": nearby_seconds,
        "normal_review_samples": expected,
        "review_spans": len(episodes),
        "spans_already_alerted_at_start": len(carried),
        "normal_review_samples_in_carried_spans": carried_count,
        "carried_span_sample_fraction": (
            round(carried_count / expected, 6) if expected else None
        ),
        "spans_started_within_window_after_event": len(adjacent),
        "normal_review_samples_in_nearby_spans": adjacent_count,
        "nearby_span_sample_fraction": (
            round(adjacent_count / expected, 6) if expected else None
        ),
        "longest_normal_review_spans": sorted(
            episodes, key=lambda e: -e["normal_review_samples"]
        )[:top],
        "notes": [
            "Carryover means a shadow warning was active when a normal-labeled span began.",
            "Temporal proximity does not prove the prior event caused later warnings.",
            "The annotation-normal class does not guarantee visually usable footage.",
            "Only numeric traces used; no images or frame inspection.",
            "Selected Day 3/Day 4 development sources are not independent heldouts.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--day3", required=True, type=Path)
    parser.add_argument("--day4", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--nearby-seconds", type=float, default=60)
    parser.add_argument("--top", type=int, default=8)
    args = parser.parse_args()
    report = {
        "status": "PHASE3D_NORMAL_REVIEW_RECOVERY_TRIAGE_DEVELOPMENT_ONLY",
        "qualified": False,
        "day3": classify(args.day3, nearby_seconds=args.nearby_seconds, top=args.top),
        "day4": classify(args.day4, nearby_seconds=args.nearby_seconds, top=args.top),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for day in ("day3", "day4"):
        data = report[day]
        print(f"\n=== {day.upper()} NORMAL-REVIEW RECOVERY TRIAGE ===")
        print(
            f"Carried over: {data['normal_review_samples_in_carried_spans']} / "
            f"{data['normal_review_samples']} flagged normal samples "
            f"({data['carried_span_sample_fraction']})"
        )
        print(
            f"Started within {data['nearby_seconds']}s of annotated event: "
            f"{data['normal_review_samples_in_nearby_spans']} flagged samples "
            f"({data['nearby_span_sample_fraction']})"
        )
        print("Top spans:", json.dumps(data["longest_normal_review_spans"][:3]))
    print("Report:", args.out.resolve())


if __name__ == "__main__":
    main()
