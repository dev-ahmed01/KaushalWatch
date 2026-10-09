"""Frozen, independently labelled apparent-operability ROI-motion trace.

Replays the *same sampling and motion calculation* the infrastructure pipeline
uses, regardless of whether an equipment-compliance case was emitted.
No RGB frames, boxes or operator identities are retained in the receipt.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
for location in (ROOT, BACKEND):
    if str(location) not in sys.path:
        sys.path.insert(0, str(location))

from app.services.operability import trace_apparent_motion
from app.services.release_assets import qualify_release_assets


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _path(root: Path, text: str) -> Path:
    path = Path(text).expanduser()
    return (path if path.is_absolute() else root / path).resolve()


def capture_operability_trace(manifest_path: Path, csv_path: Path) -> dict:
    manifest_path = Path(manifest_path).expanduser().resolve()
    csv_path = Path(csv_path).expanduser().resolve()
    qualification = qualify_release_assets(manifest_path)
    if not qualification["ready"]:
        raise ValueError("Release asset manifest not qualified for apparent-operability measurement")
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    root = manifest_path.parent
    frozen_label = next(row for row in data["annotations"] if row["kind"] == "operability")
    if csv_path != _path(root, frozen_label["path"]) or _sha(csv_path) != frozen_label["sha256"].lower():
        raise ValueError("Apparent-operability CSV is not the exact frozen annotation source")

    cfg = data.get("operability")
    if not isinstance(cfg, dict):
        raise ValueError("Frozen ROI configuration missing")
    asset = next(row for row in data["assets"] if row["role"] == "operability")
    if cfg.get("asset_id") != asset["id"]:
        raise ValueError("Frozen operability asset ID differs from selected clip")
    item_id = cfg.get("item_id")
    if not isinstance(item_id, str) or not item_id.strip():
        raise ValueError("Frozen operability item_id must be named")
    video = _path(root, asset["path"])
    if _sha(video) != asset["sha256"].lower():
        raise ValueError("Frozen apparent-operability source video SHA mismatch")

    roi = cfg.get("roi") or {}
    window = cfg.get("window") or {}
    try:
        coords = tuple(roi[name] for name in ("x1", "y1", "x2", "y2"))
        times = (float(window["start_sec"]), float(window["end_sec"]))
        threshold = float(cfg.get("motion_threshold", 0.8))
        max_frames = cfg.get("max_frames", 30)
    except (KeyError, ValueError, TypeError) as exc:
        raise ValueError("Frozen operability ROI, time window or threshold is invalid") from exc
    if any(type(x) is not int for x in coords):
        raise ValueError("Frozen ROI must contain integer pixel coordinates")
    if not math.isfinite(threshold) or threshold < 0:
        raise ValueError("Operability motion threshold must be finite and nonnegative")
    if type(max_frames) is not int or max_frames < 3:
        raise ValueError("Operability frame cap must be an integer >= 3")

    with csv_path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream, strict=True)
        required = {
            "sample_id", "item_id", "true_state", "pred_state",
            "source_asset_id", "centre_id", "batch_id",
        }
        columns = reader.fieldnames or []
        if len(set(columns)) != len(columns) or not required.issubset(columns):
            raise ValueError("Operability CSV needs exactly mapped item, asset, centre and batch columns")
        rows = list(reader)
    if len(rows) != 1:
        raise ValueError("One frozen ROI/window must map to exactly one operability opportunity")
    row = rows[0]
    if not isinstance(row.get("sample_id"), str) or not row["sample_id"].strip():
        raise ValueError("Operability sample_id cannot be empty")
    if row["item_id"].strip() != item_id:
        raise ValueError("Operability item_id differs from frozen ROI item")
    if row["source_asset_id"].strip() != asset["id"]:
        raise ValueError("Operability source asset differs from frozen clip")
    if (row["centre_id"].strip() != asset["centre_id"]
            or row["batch_id"].strip() != asset["batch_id"]):
        raise ValueError("Operability centre/batch differs from frozen clip")
    truth = row["true_state"].strip().upper()
    if truth not in {"APPARENTLY_ACTIVE", "APPARENTLY_INACTIVE"}:
        raise ValueError("Operability ground truth must be independently labelled ACTIVE or INACTIVE")

    motion = trace_apparent_motion(
        video, coords, threshold=threshold, max_frames=max_frames, window=times
    )
    state = motion["state"]
    if row["pred_state"].strip().upper() != state:
        raise ValueError("Operability pred_state differs from the operational ROI-motion proxy")
    if _sha(video) != asset["sha256"].lower():
        raise ValueError("Operability source changed during replay")
    return {
        "schema_version": 1,
        "receipt_type": "replayed_operability_roi_motion",
        "manifest_sha256": qualification["manifest_sha256"],
        "source_video_sha256": asset["sha256"].lower(),
        "annotation_csv_sha256": frozen_label["sha256"].lower(),
        "sample_id": row["sample_id"].strip(),
        "item_id": item_id,
        "centre_id": asset["centre_id"],
        "batch_id": asset["batch_id"],
        "source_asset_id": asset["id"],
        "motion": motion,
        "independent_label_in_csv": truth,
        "proxy_execution_recomputed_locally": True,
        "equipment_mechanical_health_verified": False,
        "claim_boundary": (
            "Same per-ROI visible-motion algorithm as the infrastructure case, replayed "
            "on SHA-frozen video; a single independently-labelled opportunity. "
            "Not equipment electrical/mechanical health, an operating-state diagnosis, "
            "or a multi-video model accuracy benchmark. Receipt is unsigned."
        ),
    }


def verify_operability_trace(manifest_path: Path, csv_path: Path, receipt_path: Path, manifest_sha256: str) -> dict:
    receipt_path = Path(receipt_path).expanduser().resolve()
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("receipt_type") != "replayed_operability_roi_motion":
        raise ValueError("Wrong or malformed apparent-operability receipt")
    if payload.get("manifest_sha256") != manifest_sha256:
        raise ValueError("Operability receipt refers to a different frozen manifest")
    current = capture_operability_trace(manifest_path, csv_path)
    if payload != current:
        raise ValueError("Apparent-operability receipt differs from re-decoded frozen source")
    return {
        "status": "local_roi_motion_replay_matched",
        "sample_id": current["sample_id"],
        "item_id": current["item_id"],
        "source_video_sha256": current["source_video_sha256"],
        "annotation_csv_sha256": current["annotation_csv_sha256"],
        "receipt_sha256": _sha(receipt_path),
        "frames_sampled": current["motion"]["frames_sampled"],
        "state": current["motion"]["state"],
        "activity_score": current["motion"]["activity_score"],
        "threshold": current["motion"]["threshold"],
        "analysis_window": current["motion"]["analysis_window"],
        "motion_proxy_replayed": True,
        "mechanical_health_verified": False,
        "claim_boundary": current["claim_boundary"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture a frozen apparent-operability ROI-motion receipt")
    parser.add_argument("--asset-manifest", required=True)
    parser.add_argument("--operability", required=True)
    parser.add_argument("--out", default="evaluation/output/final-demo/operability-receipt.json")
    args = parser.parse_args()
    dest = Path(args.out).expanduser().resolve()
    sources = {Path(args.asset_manifest).expanduser().resolve(), Path(args.operability).expanduser().resolve()}
    if dest in sources:
        parser.error("Receipt must not overwrite a frozen input")
    receipt = capture_operability_trace(Path(args.asset_manifest), Path(args.operability))
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "receipt": str(dest),
        "result": receipt["motion"]["state"],
        "frames_sampled": receipt["motion"]["frames_sampled"],
        "equipment_mechanical_health_verified": False,
        "claim_boundary": receipt["claim_boundary"],
    }, indent=2))


if __name__ == "__main__":
    main()
