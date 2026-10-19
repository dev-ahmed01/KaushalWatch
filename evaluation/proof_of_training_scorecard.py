"""Assemble an honest, SHA-pinned judge scorecard from existing receipts only.

No inference performed here. This is an INTEGRITY and ADMISSION summary.
No input receipt, even one reporting 'qualified', can turn an unsigned local
evaluation into external audited deployment approval.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path

PILLARS = ("attendance", "camera_trust", "equipment_count",
           "equipment_localization", "practical_activity", "offline_transport")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def empty_card(kind: str) -> dict:
    return {"id": kind, "state": "not_qualified",
            "metric": None, "support": None,
            "reason": "Independent source/model/reviewer evidence not admitted"}


def _safe_count(value: object) -> int:
    if type(value) is not int or not 0 <= value <= 1000000000:
        raise ValueError("Invalid count in receipt")
    return value


def _offline(record: object) -> dict:
    if (not isinstance(record, dict)
        or record.get("schema") != "KW_OFFLINE_TRANSPORT_DRILL_V1"
        or record.get("status") != "measured_loopback_fixture_not_field_qualified"
        or record.get("fixture") is not True
        or record.get("raw_video_uploaded") is not False
        or record.get("network_cut_verified") is not True
        or record.get("queue_survived_restart") is not True
        or record.get("lost_ack_idempotent_reack") is not True):
        raise ValueError("Nonconforming loopback transport receipt")
    queued, delivered, remaining = map(_safe_count,
        (record.get("queued_before"), record.get("delivered"), record.get("remaining")))
    request_bytes = _safe_count(record.get("observed_request_body_bytes_final"))
    response_bytes = _safe_count(record.get("observed_response_body_bytes_final"))
    if queued == 0 or queued != delivered + remaining or request_bytes == 0 or response_bytes == 0:
        raise ValueError("Measured transport counters contradict each other")
    return {"id": "offline_transport", "state": "measured_loopback_fixture_only",
            "metric": {"request_body_bytes": request_bytes, "response_body_bytes": response_bytes,
                       "delivered": delivered, "queued": queued},
            "support": {"network_cut_verified": True, "duplicate_reack": True},
            "reason": "Actual localhost HTTP bodies only; not an Internet bandwidth or field camera benchmark"}


def _localization(record: object) -> dict:
    if (not isinstance(record, dict)
        or record.get("schema") != "KW_EQUIPMENT_LOCALIZATION_RECEIPT_V1"
        or record.get("qualified") is not False):
        raise ValueError("Unrecognized localization receipt")
    state = record.get("status")
    if state in {"synthetic_localization_test_not_qualified", "localization_blocked"}:
        return empty_card("equipment_localization")
    if state != "localization_measured_pending_independent_audit":
        raise ValueError("Unknown localization status")
    provenance = record.get("provenance")
    if not isinstance(provenance, dict) or provenance.get("prediction_source") != "offline_groundingdino":
        raise ValueError("Localization measurement not backed by a real pinned model proposal")
    checks = ("localization_manifest_sha256", "presence_protocol_sha256", "prompts_sha256")
    if any(not isinstance(provenance.get(k), str) or not HEX64.fullmatch(provenance[k]) for k in checks):
        raise ValueError("Localization provenance missing")
    source = provenance.get("source_video_sha256_by_scene")
    annotations = provenance.get("annotations_sha256_by_scene")
    if (not isinstance(source, dict) or not isinstance(annotations, dict)
        or len(source)<4 or set(source)!=set(annotations)
        or any(not isinstance(v, str) or not HEX64.fullmatch(v)
               for v in list(source.values())+list(annotations.values()))):
        raise ValueError("Incomplete independent source/label digests")
    metrics = record.get("metrics")
    per_class = record.get("per_class")
    if not isinstance(metrics, dict) or not isinstance(per_class, dict) or not per_class:
        raise ValueError("Incomplete per-class box metrics")
    clean = {}
    for name, row in per_class.items():
        if (not isinstance(name, str) or not re.fullmatch(r"[a-z0-9_]{2,64}",name)
            or not isinstance(row, dict)):
            raise ValueError("Invalid per-class localization row")
        tp, fp, fn = [_safe_count(row.get(k)) for k in ("tp","fp","fn")]
        clean[name] = {"tp":tp,"fp":fp,"fn":fn,
                       "precision": tp/(tp+fp) if tp+fp else None,
                       "recall":tp/(tp+fn) if tp+fn else None}
    for field in ("tp","fp","fn"):
        if sum(v[field] for v in clean.values()) != _safe_count(metrics.get(field)):
            raise ValueError("Inconsistent localization totals")
    return {"id":"equipment_localization",
            "state":"candidate_measured_not_independently_qualified",
            "metric":{"tp":metrics["tp"],"fp":metrics["fp"],"fn":metrics["fn"],
                      "per_class":clean},
            "support":{"recordings":len(source)},
            "reason":"Offline model proposal vs declared blinded labels; independent audit and field acceptance absent"}


def assemble(manifest_path: Path | None) -> dict:
    report={"schema":"KW_PROOF_OF_TRAINING_SCORECARD_V1",
            "qualified":False,"scope":"controlled_source_receipts_not_field_certification",
            "pillars":{key:empty_card(key) for key in PILLARS},
            "receipt_sha256":{},
            "limitations":"No signed independent site audit, authenticated official attendance integration or sanctioned equipment counts are claimed."}
    if manifest_path is None:
        return report
    manifest_path=Path(manifest_path).expanduser().resolve()
    metadata=json.loads(manifest_path.read_text(encoding="utf-8"))
    if (not isinstance(metadata, dict)
        or set(metadata)!={"schema","status","receipts"}
        or metadata["schema"]!="KW_SCORECARD_INPUTS_V1"
        or metadata["status"]!="frozen"
        or not isinstance(metadata["receipts"],dict)
        or not set(metadata["receipts"]).issubset(set(PILLARS))):
        raise ValueError("Unfrozen scorecard receipt list")
    if len(metadata["receipts"]) != len(set(metadata["receipts"])):
        raise ValueError("Duplicate metric evidence")
    for kind,spec in metadata["receipts"].items():
        if (not isinstance(spec,dict) or set(spec)!={"path","sha256"}
            or not isinstance(spec["path"],str)
            or not isinstance(spec["sha256"],str)
            or not HEX64.fullmatch(spec["sha256"])):
            raise ValueError("Invalid scorecard input SHA")
        root=manifest_path.parent
        file=(root/spec["path"]).resolve()
        if (file==manifest_path or not file.is_relative_to(root)
            or not file.is_file() or file.stat().st_size>500000
            or digest(file)!=spec["sha256"]):
            raise ValueError("Scorecard receipt missing, external, changed or oversized")
        doc=json.loads(file.read_text(encoding="utf-8"))
        report["receipt_sha256"][kind]=spec["sha256"]
        if kind=="offline_transport":
            report["pillars"][kind]=_offline(doc)
        elif kind=="equipment_localization":
            report["pillars"][kind]=_localization(doc)
        else:
            # Other existing report formats have different predictor provenance
            # limits. Do not launder them into qualified numbers by trusting
            # arbitrary booleans or manually filled spreadsheet columns.
            report["pillars"][kind]["reason"]="Receipt file SHA matched; independent model-source qualification still not established"
    return report


def main() -> None:
    p=argparse.ArgumentParser(description="Private frozen source receipt qualification scorecard")
    p.add_argument("--manifest",type=Path)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    try:
        output=assemble(args.manifest)
    except (ValueError,OSError,TypeError,KeyError,json.JSONDecodeError):
        output=assemble(None)
        output["status"]="blocked_source_or_receipt_mismatch"
        failed=True
    else:
        output["status"]="evidence_gates_reported_not_field_qualified"
        failed=False
    target=args.out.expanduser().resolve()
    if target.exists():raise SystemExit("Refusing to replace an existing private scorecard")
    target.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"w",encoding="utf-8") as h:
        json.dump(output,h,indent=2,sort_keys=True)
        h.write("\n")
    print(json.dumps({"status":output["status"],"qualified":False}))
    if failed:raise SystemExit(2)


if __name__=="__main__":
    main()
