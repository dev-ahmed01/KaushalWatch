"""Independent model-only equipment presence/count qualification.

Exercises the OPTIONAL local GroundingDINO adapter on pinned held-out clips.
It is not object-localization mAP, authorised quantity compliance, or machine
health. No human-reviewed correction is ever provided to the model.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
for parent in (ROOT, ROOT/"backend"):
    if str(parent) not in sys.path:
        sys.path.insert(0, str(parent))
from evaluation.heldout_qualification import sha256_file
from app.services.live_equipment import GroundingDinoAdapter, verify_model_snapshot

POLICY = {
    "policy_id": "live-equipment-heldout-provisional-v1",
    "min_heldout_recordings": 4,
    "min_sites": 2,
    "min_cameras": 2,
    "min_items": 2,
    "min_positive_opportunities": 4,
    "min_negative_opportunities": 4,
    "min_proposal_recall": 0.80,
    "max_false_presence_rate": 0.15,
    "max_count_mae": 0.80,
}
HEX = set("0123456789abcdef")


def _file(root: Path, entry: object, label: str) -> Path:
    if not isinstance(entry, dict) or set(entry) != {"path","sha256"}:
        raise ValueError(f"{label} requires path and SHA-256")
    value, digest = entry["path"], entry["sha256"]
    if (not isinstance(value, str) or not value or not isinstance(digest,str)
        or len(digest)!=64 or any(x not in HEX for x in digest)):
        raise ValueError(f"{label}: invalid path/SHA pin")
    path = (root/value).resolve()
    if not path.is_file() or not path.stat().st_size or sha256_file(path)!=digest:
        raise ValueError(f"{label}: missing file or SHA-256 mismatch")
    return path


def _identifier(value: object, label: str) -> str:
    if (not isinstance(value,str) or not 3<=len(value)<=100
        or any(not (x.isalnum() or x in "_-.") for x in value)):
        raise ValueError(f"Invalid {label} identifier")
    return value


def load(manifest: Path, *, test_fixture: bool = False) -> dict:
    manifest=Path(manifest).expanduser().resolve()
    if not manifest.is_file():
        raise ValueError("Live equipment held-out manifest is missing")
    doc=json.loads(manifest.read_text(encoding="utf-8"))
    if (not isinstance(doc,dict) or doc.get("schema_version")!=1
        or doc.get("status")!="frozen" or doc.get("policy")!=POLICY
        or type(doc.get("fixture_only")) is not bool):
        raise ValueError("Equipment protocol must be frozen with the exact provisional policy")
    if doc["fixture_only"] and not test_fixture:
        raise ValueError("Synthetic equipment data cannot qualify a real detector")
    _identifier(doc.get("protocol_id"),"protocol")
    model=doc.get("model")
    if not isinstance(model,dict) or set(model)!={"directory","files","prompts","threshold","nms_iou","device"}:
        raise ValueError("Frozen model snapshot, prompts and parameters required")
    dirname=model["directory"]
    if not isinstance(dirname,str) or not dirname:
        raise ValueError("Pinned local model directory required")
    model_dir=(manifest.parent/dirname).resolve()
    # No model downloads, floating hub IDs or arbitrary code.
    digests=verify_model_snapshot(model_dir,model["files"])
    prompts=model["prompts"]
    if not isinstance(prompts,dict) or not 2<=len(prompts)<=24:
        raise ValueError("Frozen item prompts are missing")
    # Validate adapter parameters without loading its heavy model libraries.
    GroundingDinoAdapter(prompts,model_dir=model_dir,model_files=digests,
                         threshold=model["threshold"],nms_iou=model["nms_iou"],device=model["device"])
    if not isinstance(doc.get("calibration"),list) or not doc["calibration"]:
        raise ValueError("Independent calibration recording partition required")
    if not isinstance(doc.get("heldout"),list) or len(doc["heldout"])<POLICY["min_heldout_recordings"]:
        raise ValueError("Insufficient held-out equipment recordings")
    used_recordings, used_digests, used_scenes=set(),set(),set()
    held=[]
    sites,cameras=set(),set()
    positives=negatives=0
    all_classes=set()
    for split in ("calibration","heldout"):
        for row in doc[split]:
            if not isinstance(row,dict):raise ValueError("Invalid equipment recording")
            rid=_identifier(row.get("recording_id"),"recording")
            sid=_identifier(row.get("scene_id"),"scene")
            site=_identifier(row.get("site_id"),"site")
            camera=_identifier(row.get("camera_id"),"camera")
            if rid in used_recordings or sid in used_scenes:
                raise ValueError("Calibration/held-out recording leakage or duplicate ID")
            used_recordings.add(rid);used_scenes.add(sid)
            path=_file(manifest.parent,row.get("video"),"equipment video")
            sha=sha256_file(path)
            if sha in used_digests:raise ValueError("Calibration/held-out media leakage")
            used_digests.add(sha)
            for f in ("source_origin","license_basis","privacy_basis"):
                value=row.get(f)
                if not isinstance(value,str) or len(value.strip())<12:
                    raise ValueError(f"{f}: meaningful provenance required")
                if not test_fixture and any(term in value.lower() for term in ("synthetic","example","unknown","placeholder")):
                    raise ValueError("Synthetic/placeholder dataset provenance cannot qualify")
            if split=="calibration":continue
            if (row.get("blinded_review") is not True or row.get("previously_inspected") is not False
                or not _identifier(row.get("reviewer_id"),"independent label reviewer")):
                raise ValueError("Untouched independent blinded annotation required")
            truth=_file(manifest.parent,row.get("labels"),"equipment ground truth")
            opportunities=[]
            pairs=set()
            second_items:dict[float,set[str]]={}
            with truth.open(newline="",encoding="utf-8-sig") as handle:
                reader=csv.DictReader(handle,strict=True)
                if reader.fieldnames!=["second","item_id","true_count"]:
                    raise ValueError("Ground truth CSV must be second,item_id,true_count")
                for label in reader:
                    raw=label["second"];item=label["item_id"];count=label["true_count"]
                    try:second=float(raw)
                    except (TypeError,ValueError):raise ValueError("Invalid equipment label timestamp") from None
                    if (not math.isfinite(second) or second<0 or item not in prompts
                        or not isinstance(count,str) or not count.isascii() or not count.isdecimal()
                        or str(int(count))!=count):
                        raise ValueError("Invalid equipment timestamp/item/count")
                    key=(second,item)
                    if key in pairs:raise ValueError("Duplicate ground truth equipment opportunity")
                    pairs.add(key);second_items.setdefault(second,set()).add(item)
                    true=int(count)
                    opportunities.append({"second":second,"item":item,"true":true})
                    positives+=int(true>0);negatives+=int(true==0);all_classes.add(item)
            if not opportunities or len(second_items)>48 or any(set(prompts)!=items for items in second_items.values()):
                raise ValueError("Every scored timestamp must label ALL frozen equipment prompts")
            import cv2
            cap=cv2.VideoCapture(str(path))
            try:
                if not cap.isOpened():raise ValueError("Held-out equipment video unreadable")
                fps=float(cap.get(cv2.CAP_PROP_FPS))
                frame_count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                if not math.isfinite(fps) or fps<=0 or frame_count<1:
                    raise ValueError("Held-out equipment video FPS/count invalid")
                duration=frame_count/fps
                if any(t>=duration for t in second_items):
                    raise ValueError("Equipment truth timestamp beyond recorded video")
            finally:cap.release()
            sites.add(site);cameras.add((site,camera))
            held.append({"video":path,"sha":sha,"scene_id":sid,
                         "labels":opportunities,"timestamps":sorted(second_items)})
    if (len(sites)<POLICY["min_sites"] or len(cameras)<POLICY["min_cameras"]
        or len(all_classes)<POLICY["min_items"]
        or positives<POLICY["min_positive_opportunities"]
        or negatives<POLICY["min_negative_opportunities"]):
        raise ValueError("Insufficient independent camera/item/positive/negative support")
    return {"manifest_sha256":sha256_file(manifest),"model_dir":model_dir,
            "model":model,"heldout":held,"sites":len(sites),"cameras":len(cameras),
            "positives":positives,"negatives":negatives,"files":digests}


def real_predictions(scene:dict, spec:dict, adapter:GroundingDinoAdapter) -> dict:
    adapter.bind_video(scene["video"],scene["sha"])
    results={}
    try:
        for second in scene["timestamps"]:
            detections=adapter.detect_at(second)
            if len(detections)!=len(spec["model"]["prompts"]):
                raise ValueError("Detector omitted a required item opportunity")
            preds={}
            for det in detections:
                if not isinstance(det,dict) or det.get("proposal_status")!="unreviewed_model_proposal":
                    raise ValueError("Detector predictions are not raw model proposals")
                item=det.get("label")
                if item not in spec["model"]["prompts"] or item in preds:
                    raise ValueError("Duplicate or unrecognized detector item")
                count=det.get("count")
                if type(count) is not int or count<0:raise ValueError("Invalid live count")
                preds[item]=count
            results[second]=preds
    finally:adapter.close()
    return results


def evaluate(manifest:Path, *, injected:Callable|None=None, test_fixture:bool=False)->dict:
    if test_fixture != (injected is not None):
        raise ValueError("Synthetic injection is permitted only for nonqualifying CI fixtures")
    p=load(manifest,test_fixture=test_fixture)
    adapter=None
    if not test_fixture:
        m=p["model"]
        adapter=GroundingDinoAdapter(m["prompts"],model_dir=p["model_dir"],model_files=p["files"],
                                     threshold=m["threshold"],nms_iou=m["nms_iou"],device=m["device"])
        adapter.setup()
    counts=Counter()
    errors=0
    per_class={}
    for scene in p["heldout"]:
        # Independent truth labels are never passed to real or test inference.
        inputs={k:v for k,v in scene.items() if k!="labels"}
        guesses=(injected(inputs,p) if test_fixture else real_predictions(inputs,p,adapter))
        if not isinstance(guesses,dict):raise ValueError("Live equipment prediction mapping missing")
        for item in scene["labels"]:
            predictions=guesses.get(item["second"])
            if not isinstance(predictions,dict) or item["item"] not in predictions:
                raise ValueError("Missing live model proposal is NOT a zero count")
            n=predictions[item["item"]]
            if type(n) is not int or n<0:raise ValueError("Invalid model count")
            truth=item["true"];errors+=abs(n-truth)
            counts["total"]+=1
            cls=per_class.setdefault(item["item"],{"sum_abs_error":0,"opportunities":0})
            cls["sum_abs_error"]+=abs(n-truth);cls["opportunities"]+=1
            counts["tp" if truth>0 and n>0 else
                   "fn" if truth>0 else
                   "fp" if n>0 else "tn"]+=1
    after=load(manifest,test_fixture=test_fixture)
    if (after["manifest_sha256"]!=p["manifest_sha256"] or after["files"]!=p["files"]
        or [s["sha"] for s in after["heldout"]] != [s["sha"] for s in p["heldout"]]):
        raise ValueError("Frozen equipment inputs changed during live inference")
    tp,fn,fp,tn=(counts[k] for k in ("tp","fn","fp","tn"))
    recall=tp/(tp+fn) if tp+fn else None
    fpr=fp/(fp+tn) if fp+tn else None
    mae=errors/counts["total"] if counts["total"] else None
    criteria={
        "proposal_presence_recall":recall is not None and recall>=POLICY["min_proposal_recall"],
        "false_presence_rate":fpr is not None and fpr<=POLICY["max_false_presence_rate"],
        "count_mae":mae is not None and mae<=POLICY["max_count_mae"],
        "full_opportunity_coverage":counts["total"]==sum(len(s["labels"]) for s in p["heldout"]),
    }
    passed=all(criteria.values()) and not test_fixture
    return {
        "qualified":passed,
        "status":"synthetic_live_detector_fixture_not_qualifying" if test_fixture else
                 "live_equipment_proposal_qualified" if passed else "live_equipment_proposal_not_qualified",
        "policy_id":POLICY["policy_id"],"criteria":criteria,
        "support":{"recordings":len(p["heldout"]),"sites":p["sites"],"cameras":p["cameras"],
                   "positive_opportunities":p["positives"],"negative_opportunities":p["negatives"]},
        "metrics":{"presence_recall":recall,"false_presence_rate":fpr,"count_mae":mae,
                   "confusion":{key:counts[key] for key in ("tp","fp","fn","tn")},
                   "per_item_mae":{k:v["sum_abs_error"]/v["opportunities"] for k,v in per_class.items()}},
        "provenance":{"manifest_sha256":p["manifest_sha256"],
                      "model_file_digests":p["files"],
                      "prediction_source":"synthetic_injected_never_qualifies" if test_fixture
                          else "actual_local_offline_groundingdino"},
        "limitations":[
            "Raw zero-shot proposal counts only; not independent box-localization mAP.",
            "No reviewer corrections are included in the model-only score.",
            "A passed presence count gate does not establish official required quantity or compliance.",
            "Dataset license, reviewer independence and absence of leakage require human audit.",
            "Synthetic fixtures never establish accuracy of any real equipment model.",
        ],
    }


def main()->None:
    p=argparse.ArgumentParser(description="Frozen held-out live equipment proposal count evaluation")
    p.add_argument("--manifest",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--check-inputs",action="store_true")
    args=p.parse_args()
    try:
        if args.check_inputs:
            d=load(args.manifest)
            report={"qualified":False,"status":"inputs_pinned_no_inference",
                    "manifest_sha256":d["manifest_sha256"]}
        else:report=evaluate(args.manifest)
    except (ValueError,OSError,RuntimeError,KeyError,TypeError,json.JSONDecodeError) as exc:
        report={"qualified":False,"status":"live_equipment_blocked","reason":str(exc)}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2))
    if report["status"]!="inputs_pinned_no_inference" and not report["qualified"]:
        raise SystemExit(2)


if __name__=="__main__":
    main()
