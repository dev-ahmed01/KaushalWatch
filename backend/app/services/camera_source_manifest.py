"""Standalone API-side validator for private Camera Trust source manifests.

The protected FastAPI image must not require the separate research workstation
package to be installed. Never return Drive IDs or credentials via API routes.
Keep format parity with the original kwtrust Drive downloader.
"""
from __future__ import annotations
import json
from pathlib import Path
import re

FILE_ID=re.compile(r"^[A-Za-z0-9_-]{12,150}$")
SAFE_FILENAME=re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,130}$")
SHA=re.compile(r"^[0-9a-f]{64}$")

def load_manifest(path:Path) -> list[dict]:
    data=json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(data,dict) or data.get("version")!="KWTRUST_DRIVE_ASSETS_V1"
        or not isinstance(data.get("files"),list)):
        raise ValueError("Unrecognized approved Drive source manifest")
    files=data["files"]
    if not 1<=len(files)<=150:
        raise ValueError("Unexpected approved Drive manifest size")
    seen=set()
    for f in files:
        if not isinstance(f,dict):
            raise ValueError("Invalid approved Drive source entry")
        fid=f.get("id")
        name=f.get("name")
        if (not isinstance(fid,str) or not FILE_ID.fullmatch(fid)
            or not isinstance(name,str) or not SAFE_FILENAME.fullmatch(name)
            or name.startswith(".") or name in seen):
            raise ValueError("Invalid or duplicate approved Drive source")
        seen.add(name)
        pinned=f.get("sha256")
        if pinned is not None and (not isinstance(pinned,str) or not SHA.fullmatch(pinned)):
            raise ValueError("Invalid pinned source SHA-256")
    return files
