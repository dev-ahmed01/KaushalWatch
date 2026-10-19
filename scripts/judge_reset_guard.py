"""Fail-closed protection before reseeding the existing local demo data directory.

This verifier must execute BEFORE prepare_demo_state --yes, since that script
intentionally clears allowlisted mutable files. Never use it for real centre data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.reset_demo_state import MUTABLE_FILES

DEMO_IDS=frozenset(("DEMO-KA-104","DEMO-KA-112","DEMO-KA-207",
                    "DEMO-KA-303","DEMO-KA-509","DEMO-KA-601"))

def _json(path:Path):
 if path.is_symlink() or path.stat().st_size>10*1024*1024:
  raise ValueError("Unsafe mutable demo state")
 return json.loads(path.read_text(encoding="utf-8"))

def validate(data_dir:Path)->dict:
 root=Path(data_dir).expanduser().resolve()
 if root==Path(root.anchor) or root.is_symlink() or not root.is_dir():
  raise ValueError("An existing ordinary demo data folder is required")
 for name in MUTABLE_FILES:
  p=root/name
  if p.exists() and not p.is_file():raise ValueError("Unsafe mutable demo file")
 cases=root/"cases.json"
 history=root/"analysis_history.json"
 index=root/"evidence_index.json"
 known={}
 for file,field in ((cases,"details"),(history,"details"),(index,"metadata")):
  if not file.exists():continue
  records=_json(file)
  if (not isinstance(records,list) or
   not all(isinstance(r,dict) and isinstance(r.get(field),dict)
   and r[field].get("simulated") is True for r in records)):
   raise ValueError("Non-simulated or unreadable records block judge reset")
  known[file.name]=len(records)
  if file!=index:
   if any(r.get("centre_id") not in DEMO_IDS for r in records):
    raise ValueError("Unknown centre in mutable demo files; reset forbidden")
 settings=root/"centre_settings.json"
 if settings.exists():
  cfg=_json(settings)
  if not isinstance(cfg,dict) or set(cfg)-DEMO_IDS:
   raise ValueError("Non-demo centre settings must never be reset")
 edge=root/"edge_events.json"
 if edge.exists():
  events=_json(edge)
  if (not isinstance(events,list) or any(
    not isinstance(r,dict) or not isinstance(r.get("payload"),dict)
    or not isinstance(r["payload"].get("details"),dict)
    or r["payload"]["details"].get("simulated") is not True
    for r in events)):
   raise ValueError("Real or unknown edge receipts block demo reset")
  known["edge_events.json"]=len(events)
 evidence=root/"evidence"
 if evidence.exists():
  if evidence.is_symlink() or not evidence.is_dir():
   raise ValueError("Unsafe evidence directory")
  entries=_json(index) if index.exists() else []
  wanted={}
  for r in entries:
   location=r.get("frame_path")
   if not isinstance(location,str):raise ValueError("Unsafe demo evidence reference")
   f=Path(location)
   if f.parent.resolve()!=evidence.resolve() or not f.name.endswith((".jpg",".jpeg",".png")):
    raise ValueError("Untrusted evidence path outside synthetic demo directory")
   if f.name in wanted:raise ValueError("Ambiguous synthetic demo evidence path")
   wanted[f.name]=r.get("sha256")
  actual={}
  for child in evidence.iterdir():
   if child.is_symlink() or not child.is_file() or child.name not in wanted or child.stat().st_size>5*1024*1024:
    raise ValueError("Unindexed evidence blocks the demo reset")
   actual[child.name]=hashlib.sha256(child.read_bytes()).hexdigest()
  if actual!=wanted:
   raise ValueError("Missing/tampered synthetic evidence blocks demo reset")
 # Never delete any existing unregistered evidence or copied videos.
 return {"safe_to_reset_simulated_state":True,
         "existing_record_counts":known,
         "raw_footage_will_be_preserved":True,
         "scope":"demo_mutable_only_not_real_or_pilot_data"}

def main():
 parser=argparse.ArgumentParser(description="Refuse unsafe judge demo reset")
 parser.add_argument("--data-dir",type=Path,default=ROOT/"data")
 args=parser.parse_args()
 try:payload=validate(args.data_dir)
 except (ValueError,OSError,TypeError,KeyError,json.JSONDecodeError) as exc:
  print(json.dumps({"safe_to_reset_simulated_state":False,
    "reason":str(exc)[:200]}))
  raise SystemExit(2) from exc
 print(json.dumps(payload,indent=2))

if __name__=="__main__":
 main()
