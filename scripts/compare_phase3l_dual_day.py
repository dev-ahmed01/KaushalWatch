#!/usr/bin/env python3
"""Compare TWO completed, hash-pinned Phase 3L development recording reports.

Do not substitute selected-window summaries or previews. Reports represent
different recordings; never learn/choose a production threshold from these
already explored datasets. No footage, identity or S3 data is transmitted.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

ALLOWED_COMPLETE = {
    "FULL_DEVELOPMENT_CAUSE_REPLAY_UNAPPROVED_REFERENCE_NOT_HELD_OUT",
    "COMPLETE_OFFLINE_REFERENCE_REPLAY_DEVELOPMENT_NOT_HELD_OUT",
}
PRESETS = (
    "frozen_baseline","photometric_defer","localized_defer",
    "photometric_or_local_defer","coherent_translation_only",
    "sustained_raw_20s",
)
EVENTS = ("covered","defocused","moved")


def _read(path: Path, name: str) -> dict:
    report=json.loads(Path(path).read_text(encoding="utf-8"))
    if (not isinstance(report,dict)
            or report.get("status") not in ALLOWED_COMPLETE
            or report.get("production_qualified") is not False
            or report.get("production_integration") is not False):
        raise ValueError(f"{name}: only unqualified COMPLETE development reports accepted")
    if (report.get("evaluated_frames") != report.get("total_frames", report.get("source_frames"))
            or type(report.get("evaluated_frames")) is not int
            or report["evaluated_frames"]<=0):
        raise ValueError(f"{name}: incomplete or inconsistent frame coverage")
    comp=report.get("counterfactual_scene_gate_comparison")
    if (not isinstance(comp,dict)
            or comp.get("status")!="FULL_RECORDING_COUNTERFACTUAL_DEVELOPMENT_NOT_HELD_OUT"
            or comp.get("production_qualified") is not False
            or comp.get("deployable_candidate_selected") is not None
            or set(comp.get("candidate_comparisons",{}))!=set(PRESETS)):
        raise ValueError(f"{name}: full counterfactual sweep is absent or unqualified")
    baseline=comp["candidate_comparisons"]["frozen_baseline"]
    raw=report.get("raw_camera_review_fraction_by_class",{}).get("normal")
    if raw is None:
        raw=report.get("normal_review_fraction")
    if (not isinstance(raw,(float,int)) or
            isinstance(raw,bool) or not math.isfinite(raw)
            or baseline.get("normal_review_fraction") is None
            or abs(raw-baseline["normal_review_fraction"])>1e-6):
        raise ValueError(f"{name}: frozen baseline fails raw replay reconciliation")
    expected=report.get("fresh_event_review_counts")
    if isinstance(expected,dict):
        for kind in EVENTS:
            if expected.get(kind,0)!=baseline["events"][kind]["fresh_review_events"]:
                raise ValueError(f"{name}: {kind} event recall differs from raw replay")
    if (type(report.get("video_sha256")) is not str
            or len(report["video_sha256"])!=64
            or not all(x in "0123456789abcdef" for x in report["video_sha256"])):
        raise ValueError(f"{name}: pinned source digest required")
    return report


def compare(day3: Path, day4: Path) -> dict:
    sources={"day3":_read(day3,"day3"),"day4":_read(day4,"day4")}
    if sources["day3"]["video_sha256"]==sources["day4"]["video_sha256"]:
        raise ValueError("Day3 and Day4 must refer to distinct pinned videos")
    result={}
    for preset in PRESETS:
        by_day={}
        any_losses=False
        improvement_both=True
        for day,report in sources.items():
            record=report["counterfactual_scene_gate_comparison"]["candidate_comparisons"][preset]
            losses=record["lost_baseline_fresh_event_start_frames"]
            any_losses_map=record["lost_baseline_any_review_event_start_frames"]
            missed=sum(len(losses[k])+len(any_losses_map[k]) for k in EVENTS)
            improvement=record["raw_normal_fraction_reduction_vs_baseline"]
            if missed:
                any_losses=True
            if improvement is None or improvement<=0:
                improvement_both=False
            by_day[day]={
                "normal_review_fraction":record["normal_review_fraction"],
                "normal_fraction_change_vs_frozen":improvement,
                "normal_episode_rate":record["normal_review_episodes_per_normal_hour"],
                "lost_baseline_fresh_events":{k:len(losses[k]) for k in EVENTS},
                "lost_baseline_any_review_events":{k:len(any_losses_map[k]) for k in EVENTS},
                "fresh_review_events_by_class":{
                    k:record["events"][k]["fresh_review_events"] for k in EVENTS
                },
                "preexisting_review_at_event_onset":{
                    k:record["events"][k]["preexisting_review_at_onset"] for k in EVENTS
                },
                "altered_raw_review_samples":record["candidate_altered_raw_review_samples"],
                "interpretation":record["interpretation"],
            }
        if preset=="frozen_baseline":
            gate="FROZEN_REFERENCE"
        elif any_losses:
            gate="BLOCKED_KNOWN_EVENT_REGRESSION_IN_DEVELOPMENT"
        elif not improvement_both:
            gate="NO_CONSISTENT_TWO_RECORDING_RAW_NORMAL_GAIN"
        else:
            gate="UNQUALIFIED_DEVELOPMENT_SIGNAL_REQUIRES_INDEPENDENT_VALIDATION"
        result[preset]={"status":gate,"day_results":by_day,"authorized_for_deployment":False}
    return {
        "status":"PHASE3L_TWO_RECORDING_DEVELOPMENT_GATE_NOT_HELD_OUT",
        "production_qualified":False,
        "source_video_sha256_by_day":{
            day:source["video_sha256"] for day,source in sources.items()
        },
        "candidate_results":result,
        "recommended_for_production":None,
        "no_automatic_policy_selection":True,
        "limitations":[
            "Both previously debugged UHCTD days are development data, not a new holdout",
            "Normal-labelled samples need independent review before called false positives",
            "Suppressing a cue can change preexisting-at-onset event score semantics",
            "Neither score proves scene cause or camera displacement",
            "Any candidate losing known event review is blocked, even if fewer normal samples alert",
            "Even an unblocked candidate needs pre-registered acceptance and independent new-camera validation",
        ],
    }


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--day3",required=True,type=Path)
    parser.add_argument("--day4",required=True,type=Path)
    parser.add_argument("--out",required=True,type=Path)
    args=parser.parse_args()
    if args.out.suffix.lower()!=".json" or args.out.exists():
        parser.error("New JSON path required; do not overwrite prior evidence")
    result=compare(args.day3,args.day4)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    with args.out.open("x",encoding="utf-8") as stream:
        json.dump(result,stream,indent=2,sort_keys=True)
        stream.write("\n")
    print(json.dumps({
        "status":result["status"],
        "candidate_gates":{k:v["status"] for k,v in result["candidate_results"].items()},
        "production_qualified":False,
        "report":str(args.out.resolve()),
    },indent=2))


if __name__=="__main__":
    main()
