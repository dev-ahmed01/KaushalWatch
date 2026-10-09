"""One-video attendance case decision matching for the frozen SIH scorecard.

This is deliberately NOT a general case TP/FP/FN/TN attribution mechanism:
one operational pipeline run corresponds to one explicitly mapped attendance
case opportunity. Other case types remain unverified CSV predictions.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from statistics import median

from evaluation.capture_attendance_inference import sha256_file
from evaluation.final_scorecard_guard import _strict_bool
from evaluation.operational_attendance_verification import verify_operational_attendance_receipt


def _percent(reported: int, observed: int) -> float:
    if reported <= 0:
        return 0.0 if observed == 0 else 100.0
    return abs(reported - observed) / reported * 100.0


def verify_attendance_case_opportunity(
    manifest_path: Path,
    attendance_csv_path: Path,
    cases_csv_path: Path,
    operational_receipt_path: Path,
    manifest_sha256: str,
    case_sample_id: str,
) -> dict:
    """Fail closed if a frozen case row disagrees with a complete engine timeline."""
    manifest_path = Path(manifest_path).expanduser().resolve()
    cases_csv_path = Path(cases_csv_path).expanduser().resolve()
    if sha256_file(manifest_path) != manifest_sha256:
        raise ValueError("Frozen case manifest SHA differs from the supplied digest")
    operational = verify_operational_attendance_receipt(
        manifest_path, attendance_csv_path, operational_receipt_path, manifest_sha256
    )
    record = json.loads(Path(operational_receipt_path).read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    attendance_asset = next(x for x in manifest["assets"] if x["role"] == "attendance")
    case_annotations = next(x for x in manifest["annotations"] if x["kind"] == "cases")
    frozen_path = Path(case_annotations["path"]).expanduser()
    if not frozen_path.is_absolute():
        frozen_path = manifest_path.parent / frozen_path
    if cases_csv_path != frozen_path.resolve():
        raise ValueError("Attendance case source is not the frozen cases CSV")
    if sha256_file(cases_csv_path) != case_annotations["sha256"].lower():
        raise ValueError("Frozen case annotation digest changed")

    if not case_sample_id or not case_sample_id.strip():
        raise ValueError("Explicit attendance case sample ID required")
    with Path(cases_csv_path).open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file, strict=True)
        required = {
            "sample_id", "case_type", "true_issue", "pred_issue",
            "source_asset_id", "centre_id", "batch_id", "reported_attendance",
        }
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("Frozen case CSV lacks source/centre/batch/reported-count mapping")
        all_rows = list(reader)
        rows = [
            x for x in all_rows
            if x.get("sample_id", "").strip() == case_sample_id
            and x.get("case_type", "").strip() == "attendance_discrepancy"
        ]
    # A single whole-video verdict must not be counted as multiple
    # independent case opportunities under different sample IDs.
    from_this_video = [
        x for x in all_rows
        if x.get("source_asset_id", "").strip() == attendance_asset["id"]
        and x.get("case_type", "").strip() == "attendance_discrepancy"
    ]
    if len(from_this_video) != 1:
        raise ValueError("One attendance video must map to exactly one attendance case opportunity")
    if len(rows) != 1:
        raise ValueError("Exactly one attendance_discrepancy opportunity must match the sample ID")
    row = rows[0]
    if row["source_asset_id"].strip() != attendance_asset["id"]:
        raise ValueError("Attendance case row source asset does not match the frozen clip")
    if (row["centre_id"].strip() != attendance_asset["centre_id"]
            or row["batch_id"].strip() != attendance_asset["batch_id"]):
        raise ValueError("Attendance case row centre or batch differs from the frozen clip")
    try:
        count = int(row["reported_attendance"].strip())
    except (ValueError, AttributeError) as exc:
        raise ValueError("Attendance case requires a valid reported attendance count") from exc
    if count < 0 or type(record["pipeline_parameters"].get("reported_attendance")) is not int:
        raise ValueError("Reported attendance must be an explicit nonnegative integer")
    if record["pipeline_parameters"]["reported_attendance"] != count:
        raise ValueError("Frozen reported count does not match the operational pipeline run")

    params = record["pipeline_parameters"]
    result = record["pipeline_result"]
    timeline = record.get("decision_timeline")
    if not isinstance(timeline, list) or not timeline:
        raise ValueError("Complete operational decision timeline missing")
    if len(timeline) != result.get("frames_sampled"):
        raise ValueError("Decision timeline is missing sampled frames")
    if result.get("detector_authoritative") is not True or result.get("detector_failures") != 0:
        raise ValueError("Attendance case trace is not an authoritative successful run")
    try:
        mismatch_threshold = float(params["mismatch_threshold_pct"])
        persistence_threshold = float(params["persistence_threshold"])
        minimum_trusted_ratio = float(params["minimum_trusted_ratio"])
        warmup_seconds = float(params["attendance_registration_seconds"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Operational receipt is missing decision thresholds") from exc
    if not (0 <= mismatch_threshold <= 100 and 0 < persistence_threshold <= 1
            and 0 < minimum_trusted_ratio <= 1 and warmup_seconds >= 0):
        raise ValueError("Invalid recorded decision thresholds")

    selected_samples = record["samples"]
    selected_by_frame = {item["frame_index"]: item for item in selected_samples}
    if len(selected_by_frame) != len(selected_samples):
        raise ValueError("Operational receipt has duplicated selected sample frames")
    seen_selected: set[int] = set()
    seen: set[int] = set()
    previous_frame = -1
    eligible_flags: list[bool] = []
    trusted_counts: list[int] = []
    trusted = 0
    for sample in timeline:
        if not isinstance(sample, dict):
            raise ValueError("Malformed operational decision timeline")
        frame = sample.get("frame_index")
        second = sample.get("second")
        if type(frame) is not int or frame <= previous_frame or frame in seen:
            raise ValueError("Operational decision timeline has duplicate/out-of-order frames")
        if not isinstance(second, (int, float)) or second < 0:
            raise ValueError("Operational decision timeline has invalid time")
        seen.add(frame)
        previous_frame = frame
        if frame in selected_by_frame:
            selected = selected_by_frame[frame]
            comparable = (
                "second", "decoded_frame_sha256", "camera_trusted",
                "detector_eligible", "raw_count", "candidate_count",
                "confirmed_count", "registered_count", "smoothed_count",
                "sample_mismatch",
            )
            if any(sample.get(key) != selected.get(key) for key in comparable):
                raise ValueError("Selected sample conflicts with complete decision timeline")
            seen_selected.add(frame)
        warm = bool(second >= warmup_seconds)
        if sample.get("warmup_complete") is not warm:
            raise ValueError("Timeline warmup flag differs from recorded sample time")
        camera = sample.get("camera_trusted")
        if type(camera) is not bool:
            raise ValueError("Timeline camera trust field must be boolean")
        if camera:
            trusted += 1
        eligible = camera and warm
        if sample.get("detector_eligible") is not eligible:
            raise ValueError("Timeline detector eligibility contradicts trust or warmup")
        if eligible:
            smoothed = sample.get("smoothed_count")
            if type(smoothed) is not int or smoothed < 0:
                raise ValueError("Eligible timeline count must be a nonnegative integer")
            trusted_counts.append(smoothed)
        mismatch = bool(
            eligible and _percent(count, sample["smoothed_count"]) >= mismatch_threshold
        )
        if sample.get("mismatch_for_persistence") is not mismatch:
            raise ValueError("Timeline mismatch flag disagrees with operational count")
        if warm:
            eligible_flags.append(mismatch)

    if seen_selected != set(selected_by_frame):
        raise ValueError("Complete decision timeline excludes selected scoring samples")
    trusted_ratio = trusted / len(timeline)
    if abs(trusted_ratio - result.get("trusted_sample_ratio", -1)) > 0.00011:
        raise ValueError("Pipeline trusted ratio does not match the full timeline")
    persistence = sum(eligible_flags) / len(eligible_flags) if eligible_flags else 0.0
    if abs(persistence - result.get("mismatch_persistence_ratio", -1)) > 0.00011:
        raise ValueError("Pipeline mismatch persistence does not match the full timeline")

    # Camera insufficiency is never counted as a negative attendance decision.
    if trusted_ratio < minimum_trusted_ratio or not trusted_counts:
        raise ValueError("Insufficient trusted video: attendance case evaluation must abstain")
    estimated = int(median(trusted_counts))
    discrepancy = _percent(count, estimated)
    if result.get("estimated_occupancy") != estimated:
        raise ValueError("Pipeline estimated attendance contradicts the decision timeline")
    if result.get("discrepancy_pct") != round(discrepancy, 2):
        raise ValueError("Pipeline attendance discrepancy contradicts the decision timeline")

    predicted_issue = bool(
        discrepancy >= mismatch_threshold and persistence >= persistence_threshold
        and any(sample.get("mismatch_for_persistence") for sample in timeline)
    )
    expected_decision = "attendance_exception" if predicted_issue else "compliant"
    expected_case = "attendance_discrepancy" if predicted_issue else None
    if result.get("decision") != expected_decision or result.get("case_type") != expected_case:
        raise ValueError("Final attendance case decision disagrees with the complete timeline")
    if _strict_bool(row["pred_issue"], "pred_issue") != predicted_issue:
        raise ValueError("Frozen case pred_issue does not match actual attendance decision")
    independently_labeled = _strict_bool(row["true_issue"], "true_issue")

    return {
        "status": "one_attendance_case_opportunity_matched_to_operational_timeline",
        "case_sample_id": case_sample_id,
        "source_role": "attendance",
        "source_video_sha256": attendance_asset["sha256"].lower(),
        "frozen_cases_csv_sha256": sha256_file(Path(cases_csv_path)),
        "operational_receipt_sha256": operational["receipt_sha256"],
        "decision": expected_decision,
        "predicted_issue": predicted_issue,
        "independent_label_in_csv": independently_labeled,
        "timeline_frames": len(timeline),
        "trusted_frame_ratio": round(trusted_ratio, 4),
        "mismatch_persistence_ratio": round(persistence, 4),
        "count_source": params["occupancy_count_source"],
        "authenticity": "unsigned_local_receipt_not_cryptographically_authenticated",
        "claim_boundary": (
            "One frozen attendance_discrepancy case opportunity tied to a whole-video "
            "temporal decision. The independent truth label is supplied, not proven; "
            "other case rows, camera trust accuracy, full network false-positive rate "
            "and officer outcomes are NOT validated by this receipt."
        ),
    }
