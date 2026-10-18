"""Validate frozen independent Camera Trust labels against numeric shadow output.

python scripts/evaluate_camera_trust_holdout.py --status
python scripts/evaluate_camera_trust_holdout.py --labels /private/labels.json \
    --predictions /private/numeric.json --output /private/evaluation.json
Never downloads source video or promotes a field release.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from evaluation.camera_trust_holdout import InvalidEvaluation,blocked_status,evaluate,read_json

def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--status",action="store_true")
    parser.add_argument("--labels",type=Path)
    parser.add_argument("--predictions",type=Path)
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    if args.status:
        if any((args.labels,args.predictions,args.output)):
            parser.error("--status cannot be combined with other arguments")
        print(json.dumps(blocked_status(),indent=2))
        return 0
    if not all((args.labels,args.predictions,args.output)):
        parser.error("Evaluation requires --labels, --predictions and --output")
    try:
        result=evaluate(read_json(args.labels),read_json(args.predictions))
    except (InvalidEvaluation,json.JSONDecodeError,OSError) as exc:
        print("Camera Trust holdout evaluation BLOCKED: "+str(exc),file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True,exist_ok=True)
    # O_EXCL and restrictive permissions avoid replacing historic receipts.
    fd=os.open(args.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"w",encoding="utf-8") as out:
        json.dump(result,out,indent=2,sort_keys=True,allow_nan=False)
        out.write("\n");out.flush();os.fsync(out.fileno())
    print(json.dumps({"field_release":result["field_release"],
                      "cases":result["source_case_count"],
                      "report_path":str(args.output)},indent=2))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
