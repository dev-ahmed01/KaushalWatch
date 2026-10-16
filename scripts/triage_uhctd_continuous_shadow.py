#!/usr/bin/env python3
"""Triage existing complete continuous shadow summaries and event CSVs.

Does not open CCTV, rerun inference, alter thresholds or claim independent
qualification. This is a numerical diagnostic for the branch-only camera
experiment, never an operational camera-integrity verdict.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

METHODS = ("spatial", "global", "fusion")
TAMPER_CLASSES = ("covered", "defocused", "moved")


def _report(summary_path: Path) -> dict:
    with summary_path.open(encoding="utf-8") as handle:
        source = json.load(handle)
    if source.get("status") != "COMPLETE_CONTINUOUS_DEVELOPMENT_NOT_HELD_OUT":
        raise ValueError("Complete continuous development summary required")
    if source.get("qualified") is not False or source.get("production_integration") is not False:
        raise ValueError("Only non-qualified and non-integrated development reports accepted")
    methods = source.get("methods")
    if not isinstance(methods, dict) or set(methods) != set(METHODS):
        raise ValueError("Incomplete/unknown continuous result methods")
    event_csv = summary_path.parent / "continuous_shadow_events.csv"
    if not event_csv.is_file():
        raise ValueError(f"Missing event CSV beside summary: {event_csv}")

    events = []
    with event_csv.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        required = {"class", "start_frame", "end_frame", "method",
                    "preexisting_at_onset", "fresh_review", "fresh_delay_seconds"}
        if not required.issubset(set(reader.fieldnames or [])):
            raise ValueError("Event CSV lacks continuous diagnostic columns")
        for row in reader:
            label, method = row["class"], row["method"]
            if label not in TAMPER_CLASSES or method not in METHODS:
                raise ValueError("Unrecognized event class or method")
            fresh, pre = row["fresh_review"], row["preexisting_at_onset"]
            if fresh not in ("True", "False") or pre not in ("True", "False"):
                raise ValueError("Invalid boolean in event CSV")
            start, end = int(row["start_frame"]), int(row["end_frame"])
            if start < 1 or end < start:
                raise ValueError("Invalid source event frame bounds")
            if fresh == "True" and not row["fresh_delay_seconds"]:
                raise ValueError("Detected event missing fresh delay")
            if fresh == "False" and row["fresh_delay_seconds"]:
                raise ValueError("Missed event includes a detected delay")
            events.append(row)

    return {
        "reference": source.get("reference_basis"),
        "evaluated_frames": source.get("evaluated_frames"),
        "normal_annotated_hours": source.get("normal_annotated_hours"),
        "unknown_by_class": source.get("low_texture_unknown_by_class"),
        "by_method": {
            name: {
                "normal_review_fraction": methods[name]["normal_review_fraction"],
                "normal_review_samples": methods[name]["normal_review_samples"],
                "normal_samples": methods[name]["normal_samples"],
                "new_normal_review_episodes_per_normal_hour":
                    methods[name]["new_normal_review_episodes_per_normal_hour"],
                "new_normal_review_episodes":
                    methods[name]["new_normal_review_episodes"],
                "events": {
                    label: methods[name]["per_class"][label]
                    for label in TAMPER_CLASSES
                },
            }
            for name in METHODS
        },
        "missed_or_preexisting_events": {
            name: [
                {
                    "class": ev["class"],
                    "start_frame": int(ev["start_frame"]),
                    "end_frame": int(ev["end_frame"]),
                    "fresh_review": ev["fresh_review"] == "True",
                    "preexisting_at_onset": ev["preexisting_at_onset"] == "True",
                }
                for ev in events
                if ev["method"] == name
                and (ev["fresh_review"] == "False"
                     or ev["preexisting_at_onset"] == "True")
            ]
            for name in METHODS
        },
        "limitations": [
            "Existing summary/CSV do not identify when during normal footage each false review occurred",
            "A review on annotation-normal video is not necessarily unusable evidence",
            "Spatial/global overlap and causes cannot be inferred from aggregate counts",
            "Time-of-day, baseline drift, blur and pedestrian influences require timestamped numerical traces",
            "Same already-inspected UHCTD sources; not an independent validation",
        ],
    }


def summarize(day3: Path, day4: Path) -> dict:
    return {
        "status": "CONTINUOUS_SHADOW_FAILURE_TRIAGE_EXISTING_REPORTS_ONLY",
        "production_qualified": False,
        "datasets": {"day3": _report(day3), "day4": _report(day4)},
        "next_experiment": (
            "Instrument numeric time-of-day normal alert transitions, "
            "shadow decision origin, quality, and reference drift; "
            "do not tune or promote with this data as held-out."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--day3", type=Path, required=True,
                        help="Existing complete Day 3 continuous_shadow_summary.json")
    parser.add_argument("--day4", type=Path, required=True,
                        help="Existing complete Day 4 continuous_shadow_summary.json")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = summarize(args.day3.resolve(), args.day4.resolve())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    for day, item in result["datasets"].items():
        print(f"\n=== {day} full recording ===")
        print(f"Normal annotated hours: {item['normal_annotated_hours']}")
        for method in METHODS:
            metrics = item["by_method"][method]
            moved = metrics["events"]["moved"]
            print(
                f"{method}: normal review fraction {metrics['normal_review_fraction']}; "
                f"new normal reviews/hour "
                f"{metrics['new_normal_review_episodes_per_normal_hour']}; "
                f"moved fresh {moved['fresh_alert_events']}/{moved['events']}"
            )
        print("Fusion missed/preexisting events:",
              json.dumps(item["missed_or_preexisting_events"]["fusion"]))
    print("Numeric triage saved to", args.out.resolve())


if __name__ == "__main__":
    main()
