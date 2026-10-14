"""Held-out visual ROI motion validation, NOT equipment operability diagnosis."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Callable

ROOT=Path(__file__).resolve().parents[1]
for directory in (ROOT,ROOT/"backend"):
    if str(directory) not in sys.path:
        sys.path.insert(0,str(directory))

from evaluation.heldout_qualification import sha256_file
from app.services.operability import trace_apparent_motion

POLICY={
    "policy_id":"apparent-roi-motion-heldout-provisional-v1",
    "min_heldout_windows":6,
    "min_sites":2,
    "min_cameras":2,
    "min_active_windows":2,
    "min_inactive_windows":2,
    "min_indeterminate_windows":1,
    "threshold":0.8,
    "min_definitive_coverage":0.85,
    "min_active_recall":0.85,
    "max_false_active_rate":0.15,
    "max_false_certainty_when_unlabelable":0.05,
}
STATES={"APPARENTLY_ACTIVE","APPARENTLY_INACTIVE","UNDETERMINABLE"}
HEX=set("0123456789abcdef")


def pinned(root:Path, spec:object)->Path:
    if not isinstance(spec,dict) or set(spec)!={"path","sha256"}:
        raise ValueError("Video requires frozen path and SHA-256")
    name,digest=spec["path"],spec["sha256"]
    if not isinstance(name,str) or not name or not isinstance(digest,str) or len(digest)!=64 or any(c not in HEX for c in digest):
        raise ValueError("Invalid operability source path or digest")
    path=(root/name).resolve()
    if not path.is_file() or not path.stat().st_size or sha256_file(path)!=digest:
        raise ValueError("Apparent-motion video SHA-256 mismatch or missing")
    return path


def ident(value:object)->str:
    if not isinstance(value,str) or not 3<=len(value)<=96 or not all(c.isalnum() or c in "_.-" for c in value):
        raise ValueError("Invalid operability identity metadata")
    return value


def load(manifest:Path,*,test_fixture:bool=False)->dict:
    manifest=Path(manifest).expanduser().resolve()
    if not manifest.is_file():raise ValueError("Operability held-out manifest is missing")
    doc=json.loads(manifest.read_text(encoding="utf-8"))
    if (not isinstance(doc,dict) or doc.get("schema_version")!=1 or doc.get("status")!="frozen"
        or doc.get("policy")!=POLICY or type(doc.get("fixture_only")) is not bool):
        raise ValueError("Frozen apparent-motion policy/fixture declaration is required")
    if doc["fixture_only"] and not test_fixture:
        raise ValueError("Synthetic apparent-motion fixture is never qualifying")
    ident(doc.get("protocol_id"))
    if not isinstance(doc.get("calibration"),list) or not doc["calibration"]:
        raise ValueError("Independent calibration recordings required")
    if not isinstance(doc.get("heldout"),list) or len(doc["heldout"])<POLICY["min_heldout_windows"]:
        raise ValueError("Insufficient new held-out ROI motion windows")
    used_ids=set();used_recordings=set();used_digests=set()
    sites=set();cameras=set();truths=Counter();scenes=[]
    for split in ("calibration","heldout"):
        for record in doc[split]:
            if not isinstance(record,dict):raise ValueError("Malformed operability recording")
            sid=ident(record.get("scene_id"))
            rid=ident(record.get("recording_id"))
            site=ident(record.get("site_id"))
            camera=ident(record.get("camera_id"))
            if sid in used_ids or rid in used_recordings:
                raise ValueError("Calibration and held-out recording leakage")
            used_ids.add(sid);used_recordings.add(rid)
            video=pinned(manifest.parent,record.get("video"))
            digest=sha256_file(video)
            if digest in used_digests:
                raise ValueError("Duplicate scene/video SHA reused as independent evidence")
            used_digests.add(digest)
            for name in ("source_origin","license_basis","privacy_basis"):
                val=record.get(name)
                if not isinstance(val,str) or len(val.strip())<12:
                    raise ValueError("Operability source, license and privacy provenance required")
                if not test_fixture and any(word in val.lower() for word in ("synthetic","example","placeholder")):
                    raise ValueError("Fixture provenance is not qualifying")
            if split=="calibration":continue
            if (record.get("blinded_review") is not True
                or record.get("previously_inspected") is not False
                or not ident(record.get("reviewer_id"))):
                raise ValueError("Independent blinded untouched labels required")
            truth=record.get("true_visible_motion")
            if truth not in STATES:raise ValueError("Truth is visible motion, not equipment health")
            roi=record.get("roi")
            window=record.get("window")
            if (not isinstance(roi,list) or len(roi)!=4
                or any(type(x) is not int or x<0 for x in roi)
                or roi[2]<=roi[0] or roi[3]<=roi[1]):
                raise ValueError("Invalid frozen ROI pixel coordinates")
            if (not isinstance(window,list) or len(window)!=2
                or any(type(x) not in (int,float) or not __import__("math").isfinite(x) for x in window)
                or window[0]<0 or window[1]<=window[0]):
                raise ValueError("Invalid frozen start/end measurement window")
            import cv2
            cap=cv2.VideoCapture(str(video))
            try:
                if not cap.isOpened():raise ValueError("Motion video could not be decoded")
                fps=float(cap.get(cv2.CAP_PROP_FPS));frames=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH));height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                if fps<=0 or frames<3 or window[1]>(frames/fps)+1e-6 or roi[2]>width or roi[3]>height:
                    raise ValueError("ROI/window out of frozen video bounds")
            finally:cap.release()
            truths[truth]+=1;sites.add(site);cameras.add((site,camera))
            scenes.append({
                "id":sid,"video":video,"roi":tuple(roi),
                "window":tuple(window),"truth":truth,
            })
    if (len(sites)<POLICY["min_sites"] or len(cameras)<POLICY["min_cameras"]
        or truths["APPARENTLY_ACTIVE"]<POLICY["min_active_windows"]
        or truths["APPARENTLY_INACTIVE"]<POLICY["min_inactive_windows"]
        or truths["UNDETERMINABLE"]<POLICY["min_indeterminate_windows"]):
        raise ValueError("Insufficient positive, negative, unlabelable or multi-camera evidence")
    return {"scenes":scenes,"sites":len(sites),"cameras":len(cameras),
            "manifest_sha256":sha256_file(manifest),
            "videos":{s["id"]:sha256_file(s["video"]) for s in scenes},
            "truths":dict(truths)}


def infer(scene:dict)->str:
    result=trace_apparent_motion(
        scene["video"],scene["roi"],
        threshold=POLICY["threshold"],max_frames=30,window=scene["window"])
    if result["method"]!="roi_motion_proxy":raise ValueError("Expected actual ROI motion sampler")
    return result["state"]


def evaluate(manifest:Path,*,injected:Callable|None=None,test_fixture:bool=False)->dict:
    if test_fixture!=(injected is not None):
        raise ValueError("Synthetic injection is allowed only for nonqualifying test fixtures")
    frozen=load(manifest,test_fixture=test_fixture)
    evaluate_scene=injected or infer
    count=Counter()
    for item in frozen["scenes"]:
        scene={k:v for k,v in item.items() if k!="truth"}
        outcome=evaluate_scene(scene)
        if outcome not in {"APPARENTLY_ACTIVE","APPARENTLY_INACTIVE","UNCERTAIN"}:
            raise ValueError("Motion proxy returned an unknown decision")
        truth=item["truth"]
        if truth=="UNDETERMINABLE":
            count["unlabelable"]+=1
            count["unsafe_certainty"]+=int(outcome!="UNCERTAIN")
            continue
        count["labelled"]+=1
        if outcome=="UNCERTAIN":
            count["abstained"]+=1
            continue
        count["definitive"]+=1
        count["tp" if truth=="APPARENTLY_ACTIVE" and outcome=="APPARENTLY_ACTIVE" else
              "fn" if truth=="APPARENTLY_ACTIVE" else
              "fp" if outcome=="APPARENTLY_ACTIVE" else "tn"]+=1
    after=load(manifest,test_fixture=test_fixture)
    if after["manifest_sha256"]!=frozen["manifest_sha256"] or after["videos"]!=frozen["videos"]:
        raise ValueError("Motion clips or labels changed after inference")
    tp,fn,fp,tn=(count[k] for k in ("tp","fn","fp","tn"))
    recall=tp/(tp+fn) if tp+fn else None
    fpr=fp/(fp+tn) if fp+tn else None
    cover=count["definitive"]/count["labelled"] if count["labelled"] else 0
    unsafe=count["unsafe_certainty"]/count["unlabelable"] if count["unlabelable"] else None
    criteria={
        "definitive_coverage":cover>=POLICY["min_definitive_coverage"],
        "active_recall":recall is not None and recall>=POLICY["min_active_recall"],
        "false_active_rate":fpr is not None and fpr<=POLICY["max_false_active_rate"],
        "uncertain_for_unlabelable":unsafe is not None and unsafe<=POLICY["max_false_certainty_when_unlabelable"],
    }
    passed=all(criteria.values()) and not test_fixture
    return {
        "qualified":passed,
        "status":"synthetic_visual_motion_fixture_not_qualifying" if test_fixture else
                 "visual_motion_proxy_qualified" if passed else "visual_motion_proxy_not_qualified",
        "policy_id":POLICY["policy_id"],"criteria":criteria,
        "support":{"scenes":len(frozen["scenes"]),"cameras":frozen["cameras"],
                   "sites":frozen["sites"],"truths":frozen["truths"]},
        "metrics":{"visible_motion_recall":recall,"false_active_rate":fpr,
                   "decision_coverage":cover,"unsafe_certainty_rate":unsafe,
                   "abstentions":count["abstained"],
                   "confusion":{k:count[k] for k in ("tp","fn","fp","tn")}},
        "provenance":{"manifest_sha256":frozen["manifest_sha256"],
                      "prediction_source":"synthetic_nonqualifying" if test_fixture else "actual_trace_apparent_motion"},
        "limitations":[
            "Visible region-of-interest motion ONLY, not mechanical/electrical health.",
            "Camera shaking, occlusion, false movement and lighting can fool the proxy.",
            "An indeterminate independent label must be an abstention, not an operating claim.",
            "Previously inspected footage cannot be an untouched real benchmark.",
            "Synthetic CI fixtures never qualify a real training-centre camera.",
        ],
    }


def main()->None:
    parser=argparse.ArgumentParser(description="Unseen multi-camera ROI motion-proxy qualification")
    parser.add_argument("--manifest",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--check-inputs",action="store_true")
    args=parser.parse_args()
    try:
        if args.check_inputs:
            data=load(args.manifest)
            report={"qualified":False,"status":"inputs_pinned_no_inference","manifest_sha256":data["manifest_sha256"]}
        else:report=evaluate(args.manifest)
    except (ValueError,OSError,TypeError,KeyError,json.JSONDecodeError) as e:
        report={"qualified":False,"status":"visual_motion_blocked","reason":str(e)}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))
    if report["status"]!="inputs_pinned_no_inference" and not report["qualified"]:
        raise SystemExit(2)


if __name__=="__main__":
    main()
