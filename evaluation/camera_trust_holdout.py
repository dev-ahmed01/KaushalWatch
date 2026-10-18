"""Offline fail-closed Camera Trust candidate validation, not physical-tamper certification.

Consumes separately frozen adjudications and SHA-pinned numeric shadow reports.
No frames, videos, threshold tuning, enforcement actions or release promotion.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any

SCHEMA = "KW_CAMERA_HOLDOUT_EVALUATION_V1"
LABEL_SCHEMA = "KW_CAMERA_INDEPENDENT_LABELS_V1"
PREDICTION_SCHEMA = "KW_CAMERA_SHADOW_PREDICTIONS_V1"
SHADOW_SCHEMA = "CAMERA_TRUST_SHADOW_SAMPLE_V1"
CLASSES = ("normal", "covered", "defocused", "moved")
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}$")
SHA = re.compile(r"^[0-9a-f]{64}$")
MAX_RECORDS = 10000
MAX_SAMPLES = 180

class InvalidEvaluation(ValueError):
    """Invalid, stale, unapproved or incomplete evidence."""

def require(condition: bool, error: str) -> None:
    if not condition:
        raise InvalidEvaluation(error)

def hash_json(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()

def read_json(path: Path) -> Any:
    size=path.stat().st_size
    require(0 < size <= 24 * 1024 * 1024, "Input JSON size outside safe bounds")
    return json.loads(path.read_text(encoding="utf-8"))

def identifier(value: Any, name: str) -> str:
    require(isinstance(value, str) and SAFE_ID.fullmatch(value) is not None,
            f"Invalid or unsafe {name}")
    return value

def sha(value: Any, name: str) -> str:
    require(isinstance(value, str) and SHA.fullmatch(value) is not None, f"Invalid {name}")
    return value

def positive_number(value: Any, name: str, upper: float = 86400*31) -> float:
    require(type(value) in (float,int) and math.isfinite(value) and
            0 < value <= upper, f"Invalid {name}")
    return float(value)

def _iso_timestamp(value: Any, name: str) -> datetime:
    require(isinstance(value, str) and 20 <= len(value) <= 40, f"Invalid {name}")
    try:
        stamp=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError:
        raise InvalidEvaluation(f"Invalid {name}") from None
    require(stamp.tzinfo is not None, f"Timezone required for {name}")
    return stamp.astimezone(timezone.utc)

def _validate_labels(labels: Any) -> dict[str,dict]:
    require(isinstance(labels,dict) and labels.get("schema")==LABEL_SCHEMA,
            "Unrecognized frozen independent label manifest")
    freeze=_iso_timestamp(labels.get("labels_frozen_at"),"labels_frozen_at")
    sha(labels.get("evaluation_policy_sha256"),"evaluation_policy_sha256")
    require(labels.get("split")=="untouched_external_holdout",
            "Evaluation must use explicitly external held-out split")
    rows=labels.get("cases")
    require(isinstance(rows,list) and 1 <= len(rows) <= MAX_RECORDS,
            "Holdout case count outside bounds")
    found={}
    for row in rows:
        require(isinstance(row,dict),"Holdout row must be object")
        case_id=identifier(row.get("case_id"),"case_id")
        require(case_id not in found,"Duplicate independently labelled case")
        site=identifier(row.get("site_id"),"site_id")
        camera=identifier(row.get("camera_id"),"camera_id")
        sha(row.get("source_sha256"),"source_sha256")
        require(row.get("label") in CLASSES,"Unsupported physical label")
        duration=positive_number(row.get("duration_seconds"),"duration_seconds")
        labeler=identifier(row.get("independent_labeler_id"),"independent_labeler_id")
        custodian=identifier(row.get("source_custodian_id"),"source_custodian_id")
        operator=identifier(row.get("inference_operator_id"),"inference_operator_id")
        require(len({labeler,custodian,operator})==3,
                "Holdout labeling, custody and inference actors must be distinct")
        reviewed=_iso_timestamp(row.get("label_adjudicated_at"),"label_adjudicated_at")
        require(reviewed <= freeze,"Physical label was adjudicated after labels frozen")
        stratum=identifier(row.get("stratum"),"stratum")
        require(row.get("label_blinded_to_predictions") is True,
                "Label reviewer must be blinded to predictions")
        require(row.get("independent_capture") is True,
                "Source must be designated independently captured")
        identifier(row.get("custody_record_id"),"custody_record_id")
        # These are unverified claims, NOT independent or cryptographic proof.
        found[case_id]=dict(row, duration_seconds=duration,site_id=site,
                            camera_id=camera,stratum=stratum)
    return found

def _validate_numeric_trace(report: Any, case: dict) -> dict:
    require(isinstance(report,dict) and report.get("schema")==SHADOW_SCHEMA,
            "Wrong shadow report schema")
    require(report.get("source_sha256")==case["source_sha256"],
            "Source digest mismatch between adjudication and frozen inference")
    require(report.get("physical_camera_health")=="UNKNOWN" and
            report.get("production_qualified") is False and
            report.get("auto_incident_mutations")==0 and
            report.get("frame_images_or_video_exported") is False,
            "Shadow analysis asserts unsupported physical or enforcement claims")
    require(report.get("sampling")=="SPARSE_RANDOM_ACCESS_NOT_FULL_VIDEO_DECODE",
            "Only explicitly declared sparse sampling supported")
    total=report.get("source_frame_count_reported")
    fps=report.get("fps_reported")
    require(type(total) is int and 2 <= total <= 2_000_000 and
            type(fps) in (int,float) and math.isfinite(fps) and fps > .1,
            "Invalid source frame count or FPS")
    tolerance=max(2.0,.02*case["duration_seconds"])
    require(abs(total/fps-case["duration_seconds"]) <= tolerance,
            "Independently reported duration differs from decoded metadata")
    samples=report.get("samples")
    expected=report.get("requested_samples")
    observed=report.get("sampled_frames")
    failed=report.get("failed_positions")
    require(type(expected) is int and 2 <= expected <= MAX_SAMPLES,
            "Requested samples outside limits")
    require(isinstance(samples,list) and len(samples)>0 and type(observed) is int and
            observed==len(samples) and len(samples)<=expected and
            isinstance(failed,list) and len(failed)+len(samples)==expected,
            "Sample accounting incomplete or inconsistent")
    failed_pos=set()
    for i in failed:
        require(type(i) is int and 0 <= i < total and i not in failed_pos,
                "Invalid or duplicate failed frame position")
        failed_pos.add(i)
    candidates=0
    previous=-1
    for sample in samples:
        require(isinstance(sample,dict),"Missing sample data")
        position=sample.get("requested_frame0")
        actual=sample.get("decoded_frame0")
        require(type(position) is int and 0 <= position < total and
                position>previous and position not in failed_pos and
                type(actual) is int and abs(actual-position)<=1,
                "Inconsistent, duplicated or mis-decoded sample position")
        previous=position
        value=sample.get("candidate_for_human_review")
        require(type(value) is bool,"Missing boolean review candidate")
        require(sample.get("physical_camera_health")=="UNKNOWN" and
                sample.get("production_qualified") is False,
                "Sample makes unsupported field accuracy claim")
        candidates+=int(value)
    require(candidates==report.get("possible_review_samples"),
            "Candidate aggregate does not match numeric trace")
    return {"candidate":candidates>0,"candidate_samples":candidates,
            "observed_samples":len(samples),"requested_samples":expected,
            "complete":len(failed)==0,
            "reference_present":report.get("authorized_reference_file_present") is True}

def _wilson(k:int,n:int) -> list[float] | None:
    if n==0:return None
    z=1.959963984540054
    p=k/n
    d=1+z*z/n
    c=(p+z*z/(2*n))/d
    m=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [round(max(0,c-m),4),round(min(1,c+m),4)]

def _cohort_summary(rows:list[dict]) -> dict:
    positive=[r for r in rows if r["label"]!="normal"]
    normal=[r for r in rows if r["label"]=="normal"]
    detected=sum(r["candidate"] for r in positive)
    flagged=sum(r["candidate"] for r in normal)
    return {"positive_clips":len(positive),
            "positive_clips_with_any_candidate":detected,
            "positive_clip_candidate_rate":round(detected/len(positive),4) if positive else None,
            "positive_clip_candidate_rate_wilson_95":_wilson(detected,len(positive)),
            "normal_clips":len(normal),"normal_clips_with_any_candidate":flagged,
            "normal_clip_candidate_rate":round(flagged/len(normal),4) if normal else None,
            "normal_clip_candidate_rate_wilson_95":_wilson(flagged,len(normal)),
            "independently_labeled_normal_video_hours":
                round(sum(r["duration_seconds"] for r in normal)/3600,6)}

def evaluate(labels:Any,predictions:Any) -> dict:
    cases=_validate_labels(labels)
    require(isinstance(predictions,dict) and predictions.get("schema")==PREDICTION_SCHEMA,
            "Unrecognized frozen inference snapshot")
    require(predictions.get("labels_sha256")==hash_json(labels),
            "Inference snapshot not bound to exact canonical frozen independent labels")
    predicted=predictions.get("predictions")
    require(isinstance(predicted,list) and len(predicted)==len(cases),
            "Predictions and independently labelled cases differ in count")
    scores={}
    for entry in predicted:
        require(isinstance(entry,dict),"Malformed predicted case")
        case_id=identifier(entry.get("case_id"),"prediction.case_id")
        require(case_id in cases and case_id not in scores,
                "Unmatched, duplicate or unknown prediction")
        scores[case_id]=_validate_numeric_trace(entry.get("report"),cases[case_id])
    require(set(scores)==set(cases),"All frozen labels must have a prediction")
    rows=[{"case_id":key,"site_id":cases[key]["site_id"],
           "camera_id":cases[key]["camera_id"],"label":cases[key]["label"],
           "stratum":cases[key]["stratum"],"duration_seconds":cases[key]["duration_seconds"],
           **scores[key]} for key in sorted(cases)]
    by_class=defaultdict(list);by_stratum=defaultdict(list);by_site=defaultdict(list)
    for r in rows:
        by_class[r["label"]].append(r)
        by_stratum[r["stratum"]].append(r)
        by_site[r["site_id"]].append(r)
    issues=[
        "Self-declared label independence and custody require external verification",
        "Sparse video-level candidates are not validated physical event detection",
        "No prospective operator alert episodes or false alarms per camera hour",
        "No independently signed field approval or live camera acceptance evidence",
    ]
    if any(not r["complete"] for r in rows):
        issues.append("At least one source contains undecoded requested positions")
    if any(not r["reference_present"] for r in rows):
        issues.append("One or more evaluations lack an approved local reference image")
    if not by_class["normal"]:issues.append("No independent normal-video exposure")
    for cls in CLASSES[1:]:
        if not by_class[cls]:issues.append(f"No independent {cls} cases")
    return {"status":SCHEMA,"labels_sha256":hash_json(labels),
            "predictions_sha256":hash_json(predictions),
            "evaluation_policy_sha256":labels["evaluation_policy_sha256"],
            "source_case_count":len(rows),
            "distinct_sites":len(by_site),
            "distinct_cameras":len({r["camera_id"] for r in rows}),
            "cohort_diagnostic":_cohort_summary(rows),
            "by_class":{name:_cohort_summary(by_class[name]) for name in CLASSES},
            "by_stratum":{name:_cohort_summary(by_stratum[name]) for name in sorted(by_stratum)},
            "by_site":{name:_cohort_summary(by_site[name]) for name in sorted(by_site)},
            "requested_samples":sum(r["requested_samples"] for r in rows),
            "decoded_samples":sum(r["observed_samples"] for r in rows),
            "incomplete_cases":sum(not r["complete"] for r in rows),
            "case_level_numeric_result_is_physical_tamper_accuracy":False,
            "false_alarms_per_camera_hour_established":False,
            "label_independence_cryptographically_verified":False,
            "qualified_for_autonomous_enforcement":False,
            "field_release":"BLOCKED_EXTERNAL_ACCEPTANCE_REQUIRED",
            "release_blockers":issues,
            "privacy":{"raw_media_exported":False,
                       "source_aliases_included":False,
                       "person_identification_performed":False}}

def blocked_status() -> dict:
    return {"status":SCHEMA,"phase7_evaluator_implemented":True,
            "field_release":"BLOCKED_NO_EXTERNAL_HOLDOUT_SUBMITTED",
            "qualified_for_autonomous_enforcement":False,
            "required_sources":[LABEL_SCHEMA,PREDICTION_SCHEMA],
            "report_is_field_accuracy":False,
            "false_alarms_per_camera_hour_established":False}
