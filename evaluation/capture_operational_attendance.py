"""Capture an auditable sample trace from the real temporal attendance engine.

Unlike raw detector-only receipts this calls VideoCompliancePipeline.run once
and records the actual candidate/confirmed/registered/smoothed count transitions.
Synthetic detectors are explicitly marked non-qualifying fixtures.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.person_detector import build_person_detector, _resolve_openvino_xml
from app.services.video_pipeline import VideoCompliancePipeline
from app.services.vision_profile import active_profile_path
from app.services.release_assets import qualify_release_assets
from evaluation.capture_attendance_inference import _attendance_entries, _source, sha256_file


def capture_operational_attendance(
    manifest_path: Path,
    csv_path: Path,
    *,
    reported_attendance: int,
    sample_every_seconds: float = 0.2,
    count_source: str = "registered",
    smoother_window: int = 5,
    detector=None,
    test_fixture: bool = False,
) -> dict:
    if isinstance(reported_attendance, bool) or reported_attendance < 0:
        raise ValueError("reported_attendance must be a nonnegative integer")
    if not (0 < sample_every_seconds <= 10):
        raise ValueError("sample_every_seconds must be in (0,10]")
    if count_source not in {"registered", "confirmed"} or smoother_window < 1:
        raise ValueError("Invalid attendance count source or smoother window")
    manifest_path = Path(manifest_path).expanduser().resolve()
    csv_path = Path(csv_path).expanduser().resolve()
    qualification = qualify_release_assets(manifest_path)
    if not qualification["ready"]:
        raise ValueError("Frozen asset qualification failed; operational receipt withheld")
    frozen = json.loads(manifest_path.read_text(encoding="utf-8"))
    attendance = next(item for item in frozen["annotations"] if item["kind"] == "attendance")
    clip = next(item for item in frozen["assets"] if item["role"] == "attendance")
    video_path = _source(manifest_path, clip)
    if csv_path != _source(manifest_path, attendance):
        raise ValueError("Attendance annotation CSV is not the frozen sample source")
    if sha256_file(csv_path) != attendance["sha256"].lower():
        raise ValueError("Frozen attendance CSV SHA-256 changed")
    if sha256_file(video_path) != clip["sha256"].lower():
        raise ValueError("Frozen attendance clip SHA-256 changed")
    schedule = _attendance_entries(csv_path)
    if test_fixture:
        if detector is None:
            raise ValueError("An explicitly supplied synthetic detector is required in test mode")
        mode = "synthetic_test_only"
        model = None
        profile = None
    else:
        if detector is not None:
            raise ValueError("Do not inject a model in qualifying OpenVINO capture mode")
        if os.getenv("KAUSHALWATCH_PERSON_DETECTOR", "").strip().lower() != "openvino":
            raise ValueError("Explicit KAUSHALWATCH_PERSON_DETECTOR=openvino is required")
        xml = _resolve_openvino_xml().resolve()
        binary = xml.with_suffix(".bin")
        profile_path = active_profile_path().resolve()
        for path in (xml, binary, profile_path):
            if not path.is_file():
                raise ValueError(f"Required OpenVINO model/profile absent: {path}")
        detector = build_person_detector()
        if detector.info.backend != "openvino" or not detector.info.authoritative:
            raise ValueError("Only authoritative OpenVINO can generate qualifying receipts")
        model = {
            "xml_path": str(xml), "xml_sha256": sha256_file(xml),
            "bin_path": str(binary), "bin_sha256": sha256_file(binary),
        }
        profile = {"path": str(profile_path), "sha256": sha256_file(profile_path)}
        mode = "authoritative_openvino_pipeline"

    captured: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="kaushalwatch-attendance-trace-") as temporary:
        evidence = Path(temporary) / "evidence"
        pipeline = VideoCompliancePipeline(evidence, Path(temporary) / "evidence.json", detector=detector)
        summary = pipeline.run(
            video_path=video_path,
            centre_id=clip["centre_id"],
            batch_id=clip["batch_id"],
            camera_id="FROZEN-ATTENDANCE-CAMERA",
            reported_attendance=reported_attendance,
            sample_every_seconds=sample_every_seconds,
            occupancy_count_source=count_source,
            occupancy_smoother_window=smoother_window,
            observation_sink=captured.append,
        )
    index = {int(item["frame_index"]): item for item in captured}
    if len(index) != len(captured):
        raise ValueError("Operational pipeline emitted duplicate frame positions")
    samples: list[dict] = []
    for sample_id, frame_index in schedule:
        if frame_index not in index:
            raise ValueError(
                f"Frozen sample {sample_id} frame={frame_index} does not coincide "
                "with a pipeline sampling position"
            )
        samples.append({"sample_id": sample_id, **index[frame_index]})
    eligible_count = sum(item["detector_eligible"] for item in samples)
    return {
        "schema_version": 1,
        "receipt_type": "operational_attendance_pipeline",
        "mode": mode,
        "manifest_sha256": qualification["manifest_sha256"],
        "attendance_source_sha256": clip["sha256"].lower(),
        "attendance_csv_sha256": attendance["sha256"].lower(),
        "detector_backend": detector.info.backend,
        "model_artifacts": model,
        "vision_profile": profile,
        "pipeline_parameters": {
            "reported_attendance": reported_attendance,
            "sample_every_seconds": float(sample_every_seconds),
            "occupancy_count_source": count_source,
            "occupancy_smoother_window": smoother_window,
        },
        "pipeline_result": {
            "decision": summary.decision,
            "case_type": summary.case.case_type if summary.case else None,
            "estimated_occupancy": summary.estimated_occupancy,
            "mismatch_persistence_ratio": summary.mismatch_persistence_ratio,
            "trusted_sample_ratio": summary.trusted_sample_ratio,
            "frames_sampled": summary.frames_sampled,
            "detector_failures": summary.detector_failures,
            "detector_authoritative": summary.detector_authoritative,
        },
        "samples": samples,
        "eligible_samples": eligible_count,
        "withheld_samples": len(samples) - eligible_count,
        "claim_boundary": (
            "Exact operational tracker/confirmation/registration/smoothed count "
            "and eligible per-sample mismatch trace. It does not independently "
            "establish ground truth or authenticate the unsigned local receipt; "
            "case-level predictions of other subsystems are not covered."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Trace real OpenVINO tracked attendance on frozen video")
    parser.add_argument("--asset-manifest", required=True)
    parser.add_argument("--attendance", required=True)
    parser.add_argument("--reported-attendance", required=True, type=int,
                        help="Explicitly stated reported count; record source/provenance separately.")
    parser.add_argument("--sample-every-seconds", type=float, default=0.2)
    parser.add_argument("--count-source", choices=["registered", "confirmed"], default="registered")
    parser.add_argument("--smoother-window", type=int, default=5)
    parser.add_argument("--out", default="evaluation/output/final-demo/operational-attendance.json")
    args = parser.parse_args()
    result = capture_operational_attendance(
        Path(args.asset_manifest), Path(args.attendance),
        reported_attendance=args.reported_attendance,
        sample_every_seconds=args.sample_every_seconds,
        count_source=args.count_source,
        smoother_window=args.smoother_window,
    )
    output = Path(args.out).expanduser().resolve()
    sources = {Path(args.asset_manifest).expanduser().resolve(),
               Path(args.attendance).expanduser().resolve()}
    if output in sources:
        raise SystemExit("Output cannot replace the source manifest or attendance annotations")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(output), "mode": result["mode"],
        "eligible_samples": result["eligible_samples"],
        "withheld_samples": result["withheld_samples"],
        "pipeline_result": result["pipeline_result"],
        "claim_boundary": result["claim_boundary"],
    }, indent=2))


if __name__ == "__main__":
    main()
