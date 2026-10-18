"""Offline externally signed Camera Trust field dossier verifier.

No auto-enforcement pathway. Never creates a signing key, never infers
custody, and does not call external network resources or any Camera API.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from evaluation.camera_trust_field_review import (FieldReviewError, blocked,
                                                   signed_dossier)

def load(path:Path):
    if not path.is_file() or path.stat().st_size > 16*1024*1024:
        raise FieldReviewError("Missing or oversized field dossier/trust anchor")
    return json.loads(path.read_text(encoding="utf-8"))

def main():
    parser=argparse.ArgumentParser(description="Review signed field evidence without authorizing enforcement")
    parser.add_argument("--status",action="store_true")
    parser.add_argument("--bundle",type=Path)
    parser.add_argument("--trusted-public-keys",type=Path)
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    if args.status:
        if args.bundle or args.trusted_public_keys or args.output:
            parser.error("Use --status alone")
        print(json.dumps(blocked(),indent=2))
        return 0
    if not all((args.bundle,args.trusted_public_keys,args.output)):
        parser.error("Signed field review requires --bundle, --trusted-public-keys and --output")
    try:
        report=signed_dossier(load(args.bundle),load(args.trusted_public_keys))
    except (OSError,json.JSONDecodeError,FieldReviewError) as exc:
        print("Camera Trust field review BLOCKED: "+str(exc),file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(args.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"w",encoding="utf-8") as out:
        json.dump(report,out,indent=2,sort_keys=True,allow_nan=False)
        out.write("\n");out.flush();os.fsync(out.fileno())
    print(json.dumps({"manual_review_readiness":report["manual_review_readiness"],
                      "autonomous_enforcement_authorized":False,
                      "report_path":str(args.output)},indent=2))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
