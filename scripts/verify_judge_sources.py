"""Verify precisely the checked-in procedural sources and issue a SHA-bound receipt.

This does not bless private CCTV, model results or a government pilot.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
STEMS=("east-corridor","training-bay","workshop-floor")
HEX=re.compile(r"^[a-f0-9]{64}$")
PROVENANCE="PROCEDURALLY_GENERATED_RECORDING_NOT_REAL_CCTV"

def sha256(file:Path)->str:
 h=hashlib.sha256()
 with file.open("rb") as stream:
  for block in iter(lambda:stream.read(1<<20),b""):
   h.update(block)
 return h.hexdigest()

def verify(root:Path)->dict:
 root=Path(root).resolve()
 media=root/"web"/"public"/"camera-trust"
 manifest=media/"manifest.json"
 if manifest.is_symlink() or not manifest.is_file() or manifest.stat().st_size>4096:
  raise ValueError("Pinned procedural source manifest missing or unsafe")
 raw=json.loads(manifest.read_text(encoding="utf-8"))
 if (not isinstance(raw,dict) or set(raw)!={"clips","schema","provenance"}
  or raw["schema"]!="KW_SUBMISSION_SAMPLE_MEDIA_V1"
  or raw["provenance"]!=PROVENANCE or not isinstance(raw["clips"],dict)
  or set(raw["clips"])!=set(STEMS)):
  raise ValueError("Wrong procedural media manifest contract")
 result={}
 for stem in STEMS:
  spec=raw["clips"][stem]
  if not isinstance(spec,dict) or set(spec)!={"sha256"} or not isinstance(spec["sha256"],str) or not HEX.fullmatch(spec["sha256"]):
   raise ValueError("Malformed source-media SHA")
  video=media/(stem+".mp4")
  if (video.is_symlink() or not video.is_file()
   or not 500<=video.stat().st_size<=128*1024
   or sha256(video)!=spec["sha256"]):
   raise ValueError("Procedural video changed or missing")
  result[stem]={"sha256":spec["sha256"],"bytes":video.stat().st_size}
 return {"schema":"KW_PHASE6_CONTROLLED_SOURCE_LOCK_V1",
  "status":"procedural_sources_verified_not_real_field_evidence",
  "qualified":False,"manifest_sha256":sha256(manifest),
  "clips":result,
  "limitations":"Generated camera-quality demonstration assets; not institutional CCTV, verified attendance, authorised equipment or human scoring."}

def main():
 p=argparse.ArgumentParser(description="Validate final procedural recorded replay SHA256")
 p.add_argument("--root",type=Path,default=ROOT)
 p.add_argument("--out",type=Path)
 args=p.parse_args()
 try:
  receipt=verify(args.root)
 except (ValueError,OSError,TypeError,KeyError,json.JSONDecodeError) as e:
  raise SystemExit("Source freeze blocked: "+str(e)) from e
 if args.out:
  target=args.out.expanduser().resolve()
  if target.exists():raise SystemExit("Refusing to overwrite a prior source lock")
  target.parent.mkdir(parents=True,exist_ok=True)
  fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
  with os.fdopen(fd,"w",encoding="utf-8") as output:
   json.dump(receipt,output,indent=2,sort_keys=True)
   output.write("\n")
 print(json.dumps(receipt,indent=2))

if __name__=="__main__":
 main()
