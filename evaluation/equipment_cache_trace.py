"""Exact equipment sample linkage to the SHA-frozen GroundingDINO review cache.

This verifies *cached* proposal and human-reviewed counts, not live model
execution, visual localization, or model-only accuracy after human corrections.
Receipts are unsigned local JSON and must be scoped accordingly.
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

from app.services.release_assets import qualify_release_assets


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _path(root: Path, name: str) -> Path:
    value = Path(name).expanduser()
    return (value if value.is_absolute() else root / value).resolve()


def _count(value: object, name: str) -> int:
    if type(value) is int:
        result = value
    elif isinstance(value, str) and value.strip().isdigit():
        result = int(value.strip())
    else:
        raise ValueError(f"{name} must be a nonnegative integer")
    if result < 0:
        raise ValueError(f"{name} cannot be negative")
    return result


def _second(value: object, name: str) -> float:
    try:
        answer = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite timestamp") from exc
    if not math.isfinite(answer) or answer < 0:
        raise ValueError(f"{name} must be a nonnegative finite timestamp")
    return answer


def capture_equipment_cache_trace(
    manifest_path: Path,
    csv_path: Path,
    *,
    basis: str = "model_proposal",
) -> dict:
    """Map every annotation opportunity to an exact recorded cache second/item."""
    if basis not in {"model_proposal", "human_reviewed"}:
        raise ValueError("basis must be model_proposal or human_reviewed")
    manifest_path = Path(manifest_path).expanduser().resolve()
    csv_path = Path(csv_path).expanduser().resolve()
    result = qualify_release_assets(manifest_path)
    if not result["ready"]:
        raise ValueError("Release asset manifest is not qualified")
    frozen = json.loads(manifest_path.read_text(encoding="utf-8"))
    root = manifest_path.parent
    annotation = next(x for x in frozen["annotations"] if x["kind"] == "equipment")
    if _path(root, annotation["path"]) != csv_path or _sha(csv_path) != annotation["sha256"].lower():
        raise ValueError("Equipment CSV path or SHA differs from the frozen manifest")
    source = next(x for x in frozen["assets"] if x["role"] == "infrastructure")
    cache_spec = frozen["equipment_cache"]
    if cache_spec["asset_id"] != source["id"]:
        raise ValueError("Equipment cache belongs to a different source asset")
    video = _path(root, source["path"])
    if _sha(video) != source["sha256"].lower():
        raise ValueError("Equipment source video no longer matches its frozen SHA")
    cache_path = _path(root, cache_spec["path"])
    meta_path = _path(root, cache_spec["metadata"]["path"])
    if _sha(cache_path) != cache_spec["sha256"].lower():
        raise ValueError("Equipment review cache differs from frozen SHA")
    if _sha(meta_path) != cache_spec["metadata"]["sha256"].lower():
        raise ValueError("Equipment review metadata differs from frozen SHA")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if meta.get("source_video", {}).get("sha256", "").lower() != source["sha256"].lower():
        raise ValueError("Equipment reviewed cache is bound to a different video")
    if not isinstance(meta.get("review"), dict) or not meta["review"]:
        raise ValueError("Equipment review attestation is missing")
    cache_rows = json.loads(cache_path.read_text(encoding="utf-8"))
    if not isinstance(cache_rows, list) or not cache_rows:
        raise ValueError("Equipment cache must contain sampled detections")

    cache_index: dict[tuple[float, str], dict] = {}
    for i, sample in enumerate(cache_rows):
        if not isinstance(sample, dict) or not isinstance(sample.get("detections"), list):
            raise ValueError(f"Equipment cache row {i} is malformed")
        second = _second(sample.get("second"), f"cache[{i}].second")
        for det in sample["detections"]:
            if not isinstance(det, dict) or not isinstance(det.get("label"), str):
                raise ValueError("Equipment cache detection label is missing")
            key = (second, det["label"].strip())
            if not key[1] or key in cache_index:
                raise ValueError("Ambiguous or duplicate equipment cache second/item pair")
            cache_index[key] = {"detection": det, "source": sample.get("source")}

    with csv_path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream, strict=True)
        fields = reader.fieldnames or []
        needed = {"sample_id", "item_id", "second", "true_count", "pred_count"}
        if len(set(fields)) != len(fields) or not needed.issubset(fields):
            raise ValueError("Equipment CSV needs unique columns including sample_id,item_id,second")
        csv_rows = list(reader)
    if not csv_rows:
        raise ValueError("No equipment scoring rows found")

    seen: set[tuple[str, str]] = set()
    sample_second: dict[str, float] = {}
    observations: list[dict] = []
    for row in csv_rows:
        sid = str(row.get("sample_id") or "").strip()
        item = str(row.get("item_id") or "").strip()
        if not sid or not item or (sid, item) in seen:
            raise ValueError("Missing or duplicated equipment sample_id/item_id opportunity")
        seen.add((sid, item))
        second = _second(row.get("second"), "annotation.second")
        if sid in sample_second and sample_second[sid] != second:
            raise ValueError("Equipment sample_id maps to conflicting cache times")
        sample_second[sid] = second
        key = (second, item)
        if key not in cache_index:
            raise ValueError(f"No exact equipment cache time/item for {sid}:{item}")
        det = cache_index[key]["detection"]
        proposal = _count(det.get("model_count"), f"{item}.model_count")
        reviewed = _count(det.get("count"), f"{item}.count")
        status = str(det.get("review_status") or "").strip()
        if status not in {"accepted", "confirmed_absent", "rejected_false_positive", "corrected_count"}:
            raise ValueError(f"Equipment {item} has no accepted human review status")
        if item not in meta["review"] or not str(meta["review"][item]).strip():
            raise ValueError(f"Equipment {item} has no metadata reviewer attestation")
        if not isinstance(cache_index[key]["source"], str) or "human_reviewed" not in cache_index[key]["source"]:
            raise ValueError("Equipment cache row does not declare a human-reviewed source")
        prediction = proposal if basis == "model_proposal" else reviewed
        if _count(row.get("pred_count"), f"{sid}.pred_count") != prediction:
            raise ValueError(f"Equipment pred_count disagrees with frozen {basis} cache for {sid}:{item}")
        _count(row.get("true_count"), f"{sid}.true_count")
        observations.append({
            "sample_id": sid, "item_id": item, "second": second,
            "model_proposal_count": proposal,
            "reviewed_count": reviewed, "review_status": status,
            "scored_prediction": prediction,
        })

    return {
        "schema_version": 1,
        "receipt_type": "sha_bound_equipment_cache_scoring",
        "basis": basis,
        "manifest_sha256": result["manifest_sha256"],
        "source_asset_id": source["id"],
        "source_video_sha256": source["sha256"].lower(),
        "annotation_csv_sha256": annotation["sha256"].lower(),
        "reviewed_cache_sha256": cache_spec["sha256"].lower(),
        "review_metadata_sha256": cache_spec["metadata"]["sha256"].lower(),
        "model_id_recorded_in_cache_metadata": meta.get("model_id"),
        "model_inference_execution_verified": False,
        "model_weights_sha256": None,
        "observations": observations,
        "claim_boundary": (
            "A deterministic match to cached GroundingDINO proposals and explicit "
            "human-reviewed counts. It is NOT a live detector run or bounding-box "
            "localization benchmark. Human-reviewed counts may not be reported as "
            "model-only accuracy; original model weights/inference were not verified."
        ),
    }


def verify_equipment_cache_receipt(manifest_path: Path, csv_path: Path, receipt_path: Path, manifest_sha256: str) -> dict:
    receipt_path = Path(receipt_path).expanduser().resolve()
    provided = json.loads(receipt_path.read_text(encoding="utf-8"))
    if not isinstance(provided, dict) or provided.get("schema_version") != 1:
        raise ValueError("Invalid equipment cache receipt schema")
    if provided.get("receipt_type") != "sha_bound_equipment_cache_scoring":
        raise ValueError("Wrong type of equipment receipt")
    if provided.get("manifest_sha256") != manifest_sha256:
        raise ValueError("Equipment receipt belongs to a different frozen manifest")
    basis = provided.get("basis")
    if basis not in {"model_proposal", "human_reviewed"}:
        raise ValueError("Invalid equipment receipt scoring basis")
    actual = capture_equipment_cache_trace(manifest_path, csv_path, basis=basis)
    if provided != actual:
        raise ValueError("Equipment receipt differs from frozen cache or scoring values")
    return {
        "status": "local_equipment_review_cache_matched",
        "basis": basis,
        "sample_item_opportunities": len(actual["observations"]),
        "reviewed_cache_sha256": actual["reviewed_cache_sha256"],
        "source_video_sha256": actual["source_video_sha256"],
        "receipt_sha256": _sha(receipt_path),
        "model_inference_execution_verified": False,
        "model_only_metric_claim_allowed": False,
        "claim_boundary": actual["claim_boundary"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Record exact frozen model-proposal vs human-reviewed equipment counts")
    parser.add_argument("--asset-manifest", required=True)
    parser.add_argument("--equipment", required=True)
    parser.add_argument("--basis", choices=["model_proposal", "human_reviewed"], default="model_proposal")
    parser.add_argument("--out", default="evaluation/output/final-demo/equipment-cache-receipt.json")
    args = parser.parse_args()
    output = Path(args.out).expanduser().resolve()
    protected = {Path(args.equipment).expanduser().resolve(), Path(args.asset_manifest).expanduser().resolve()}
    if output in protected:
        parser.error("Receipt must not overwrite a frozen source input")
    receipt = capture_equipment_cache_trace(Path(args.asset_manifest), Path(args.equipment), basis=args.basis)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(output), "basis": args.basis, "samples": len(receipt["observations"]),
        "model_inference_execution_verified": False, "claim_boundary": receipt["claim_boundary"],
    }, indent=2))


if __name__ == "__main__":
    main()
