"""Run locally pinned GroundingDINO equipment inference, without API/cache fallback.

An OFFLINE operator tool: no video pixels uploaded or private backend credentials.
Creates a private, local proposal receipt. It never creates a compliance case
until an authorized reviewer separately accepts evidence and quantity policy.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
for folder in (ROOT,ROOT/"backend"):
    if str(folder) not in sys.path:
        sys.path.insert(0,str(folder))
from evaluation.heldout_qualification import sha256_file
from app.services.live_equipment import GroundingDinoAdapter,verify_model_snapshot


def run(spec_path:Path)->dict:
    spec_path=Path(spec_path).expanduser().resolve()
    if not spec_path.is_file():raise ValueError("Equipment inference manifest is missing")
    manifest_digest=sha256_file(spec_path)
    raw=json.loads(spec_path.read_text(encoding="utf-8"))
    if not isinstance(raw,dict) or raw.get("schema_version")!=1 or raw.get("status")!="frozen":
        raise ValueError("Offline inference requires an operator-frozen manifest")
    model=raw.get("model",{})
    if not isinstance(model,dict) or set(model)!={"directory","files","prompts","threshold","nms_iou","device"}:
        raise ValueError("Frozen equipment model configuration is incomplete")
    model_dir=(spec_path.parent/model["directory"]).resolve()
    pinned=verify_model_snapshot(model_dir,model["files"])
    media=raw.get("video")
    if not isinstance(media,dict) or set(media)!={"path","sha256"}:
        raise ValueError("Source video needs a pinned path and SHA-256")
    clip=(spec_path.parent/media["path"]).resolve()
    if (not clip.is_file() or not isinstance(media["sha256"],str)
        or sha256_file(clip)!=media["sha256"]):
        raise ValueError("Equipment source video SHA-256 changed")
    seconds=raw.get("sample_seconds")
    if (not isinstance(seconds,list) or not 1<=len(seconds)<=48
        or any(type(t) not in (int,float) or not __import__("math").isfinite(t) or t<0 for t in seconds)
        or len(set(seconds))!=len(seconds)):
        raise ValueError("Frozen source needs 1..48 unique finite sample timestamps")
    detector=GroundingDinoAdapter(model["prompts"],model_dir=model_dir,
                                  model_files=pinned,threshold=model["threshold"],
                                  nms_iou=model["nms_iou"],device=model["device"])
    detector.setup()
    detector.bind_video(clip,media["sha256"])
    rows=[]
    try:
        for second in seconds:
            predictions=detector.detect_at(float(second))
            if len(predictions)!=len(model["prompts"]):
                raise ValueError("A live detector must report every requested class")
            rows.append({
                "second":float(second),
                "source":"groundingdino_local_pinned_unreviewed",
                "detections":predictions,
            })
    finally:detector.close()
    if sha256_file(spec_path)!=manifest_digest:
        raise ValueError("Frozen operator manifest changed during inference")
    if sha256_file(clip)!=media["sha256"] or verify_model_snapshot(model_dir,pinned)!=pinned:
        raise ValueError("Source/model changed during live inference")
    return {
        "status":"live_unreviewed_equipment_proposals",
        "qualified":False,
        "model_inference_executed":True,
        "model_snapshot_sha256":pinned,
        "source_video_sha256":media["sha256"],
        "frozen_manifest_sha256":manifest_digest,
        "proposal_rows":rows,
        "claim_boundary":"Model proposals only. Missing predictions/error never mean zero; officer verification is required. No equipment operability, required quantity or compliance is established.",
    }


def main()->None:
    p=argparse.ArgumentParser(description="Offline pinned model equipment proposals")
    p.add_argument("--manifest",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    try:
        report=run(args.manifest)
    except (ValueError,OSError,RuntimeError,TypeError,KeyError,json.JSONDecodeError) as exc:
        print(f"Equipment inference blocked: {type(exc).__name__}",file=sys.stderr)
        raise SystemExit(2) from None
    target=args.out.expanduser().resolve()
    if target.exists():raise SystemExit("Refusing to replace an existing private equipment receipt")
    target.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"w",encoding="utf-8") as handle:
        json.dump(report,handle,indent=2)
        handle.write("\n")
    print(json.dumps({
        "status":report["status"],"qualified":False,
        "sample_count":len(report["proposal_rows"]),
        "private_file_created":True
    }))


if __name__=="__main__":
    main()
