"""Fail-closed, centre-specific allowlist for private SHA-pinned Drive sources.

A historical workstation manifest authenticates source identity, NOT centre
ownership. Never let a centre officer enroll arbitrary assets found in Drive.
Grant configuration lives in deployment secrets, not this public repository.
"""
from __future__ import annotations

import json
import os
import re

from fastapi import HTTPException

ALIAS = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,130}$")
VIDEO_SUFFIXES = (".avi", ".mp4", ".mov", ".mkv", ".mpeg", ".mpg")

def permitted_aliases(centre_id: str, manifest: list[dict], raw_grants: str | None = None) -> list[str]:
    raw=raw_grants if raw_grants is not None else os.getenv("KAUSHALWATCH_CAMERA_SOURCE_GRANTS_JSON","")
    try:
        grants=json.loads(raw)
    except (TypeError,ValueError):
        raise HTTPException(503,"Camera source grants are not configured") from None
    from app.services.demo_network import provisioned_centre_ids
    valid=provisioned_centre_ids()
    if not isinstance(grants,dict) or not grants or not set(grants).issubset(valid):
        raise HTTPException(503,"Camera source grants are invalid")
    manifest_names={row["name"] for row in manifest
                    if isinstance(row.get("name"),str) and
                    re.fullmatch("[0-9a-f]{64}",row.get("sha256","")) and
                    row["name"].lower().endswith(VIDEO_SUFFIXES)}
    used=set()
    for key,aliases in grants.items():
        if (not isinstance(aliases,list) or not aliases or len(aliases)>150 or
            any(not isinstance(name,str) or not ALIAS.fullmatch(name) or
                name not in manifest_names for name in aliases) or
            len(set(aliases)) != len(aliases)):
            raise HTTPException(503,"Camera source grants contain invalid entries")
        overlap=used.intersection(aliases)
        if overlap:
            # One source identity should never silently cross tenant boundaries.
            raise HTTPException(503,"Camera source grant collision")
        used.update(aliases)
    if centre_id not in valid:
        raise HTTPException(404,"Centre not found")
    return sorted(grants.get(centre_id,[]))

def require_source(centre_id: str, alias: str, manifest: list[dict]) -> dict:
    if not isinstance(alias,str) or not ALIAS.fullmatch(alias):
        raise HTTPException(422,"Invalid camera source alias")
    allowed=permitted_aliases(centre_id,manifest)
    if alias not in allowed:
        # Hide whether an alias exists outside this centre.
        raise HTTPException(404,"Camera source not available for centre")
    matches=[row for row in manifest if row["name"]==alias]
    if len(matches)!=1 or not re.fullmatch("[0-9a-f]{64}",matches[0].get("sha256","")):
        raise HTTPException(503,"Approved source hash is unavailable")
    return matches[0]
