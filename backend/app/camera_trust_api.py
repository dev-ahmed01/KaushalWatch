"""Centre-scoped officer-only Camera Trust shadow API.

No operational incident mutation, source media serving, approval self-signing
or production qualification endpoints. Existing protected BFF owns sessions.
"""
from __future__ import annotations
from datetime import datetime
import json
import os
from pathlib import Path
import re

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.services.officer_permissions import require_centre, require_write
from app.services.review_access import resolve_review_actor
from app.services.demo_network import provisioned_centre_ids
from app.services import camera_trust_store as db
from app.services.camera_sources import permitted_aliases, require_source

router=APIRouter(prefix="/api/centres/{centre_id}/camera-trust",tags=["Camera Trust shadow"])
ALIAS=re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,130}$")
SHA=re.compile(r"^[0-9a-f]{64}$")

class CameraIn(BaseModel):
    label: str=Field(min_length=3,max_length=80)
    source_alias: str=Field(min_length=1,max_length=131)

class ReferenceIn(BaseModel):
    sha256: str=Field(min_length=64,max_length=64)
    captured_at: datetime
    custody_note: str=Field(min_length=15,max_length=1000)

class DecisionIn(BaseModel):
    approve: bool

class JobIn(BaseModel):
    idempotency_key: str=Field(min_length=8,max_length=100)
    sample_limit: int=Field(default=48,ge=12,le=180)

class ReviewIn(BaseModel):
    decision: str
    note: str=Field(min_length=12,max_length=2000)

def _centre(request:Request,centre_id:str,write:bool=False) -> None:
    if centre_id not in provisioned_centre_ids():raise HTTPException(404,"Centre not found")
    require_centre(request,centre_id,write=write)
    if os.getenv("KAUSHALWATCH_STORAGE_BACKEND","json")!="postgres":
        raise HTTPException(503,"Camera Trust requires migrated PostgreSQL storage")

def _actor(request:Request) -> str:
    return getattr(request.state,"protected_officer_actor",None) or resolve_review_actor(request)

def _manifest() -> list[dict]:
    path=os.getenv("KAUSHALWATCH_CAMERA_DRIVE_MANIFEST","")
    if not path or not Path(path).is_file():
        raise HTTPException(503,"Private approved source manifest is not configured")
    try:
        from app.services.camera_source_manifest import load_manifest
        return load_manifest(Path(path))
    except (ValueError,OSError,KeyError,json.JSONDecodeError):
        raise HTTPException(503,"Approved source manifest is invalid") from None

def _source(centre_id:str,alias:str) -> dict:
    return require_source(centre_id,alias,_manifest())

@router.get("/available-sources")
def available_sources(centre_id:str,request:Request):
    _centre(request,centre_id)
    return {"sources":[{"alias":name} for name in permitted_aliases(centre_id,_manifest())]}

@router.get("")
def overview(centre_id:str,request:Request):
    _centre(request,centre_id)
    return {"release_gate":"NOT_PRODUCTION_QUALIFIED",
            "operational_mutation_enabled":False,
            "physical_camera_health":"UNKNOWN",
            "cameras":db.list_cameras(centre_id)}

@router.post("/cameras",status_code=201)
def register(centre_id:str,body:CameraIn,request:Request):
    _centre(request,centre_id,True)
    _source(centre_id,body.source_alias)
    return db.register_camera(centre_id,body.label.strip(),body.source_alias,_actor(request))

@router.get("/{camera_id}/references")
def references(centre_id:str,camera_id:str,request:Request):
    _centre(request,centre_id)
    return {"references":db.list_references(centre_id,camera_id)}

@router.post("/{camera_id}/references",status_code=201)
def propose(centre_id:str,camera_id:str,body:ReferenceIn,request:Request):
    _centre(request,centre_id,True)
    if not SHA.fullmatch(body.sha256):raise HTTPException(422,"Invalid SHA-256")
    if body.captured_at.tzinfo is None:raise HTTPException(422,"Time must have timezone")
    return db.propose_reference(centre_id,camera_id,body.sha256,body.captured_at,
                                body.custody_note.strip(),_actor(request))

@router.post("/{camera_id}/references/{reference_id}/decision")
def reference_decision(centre_id:str,camera_id:str,reference_id:str,
                       body:DecisionIn,request:Request):
    _centre(request,centre_id,True)
    return db.decide_reference(centre_id,camera_id,reference_id,body.approve,_actor(request))

@router.post("/{camera_id}/jobs",status_code=202)
def start_job(centre_id:str,camera_id:str,body:JobIn,request:Request):
    _centre(request,centre_id,True)
    if not ALIAS.fullmatch(body.idempotency_key):
        raise HTTPException(422,"Invalid idempotency key")
    cameras=db.list_cameras(centre_id)
    found=[c for c in cameras if c["camera_id"]==camera_id]
    if not found:raise HTTPException(404,"Camera not found")
    source=_source(centre_id,found[0]["source_alias"])
    return db.queue_job(centre_id,camera_id,source["name"],source["sha256"],
                        body.idempotency_key,body.sample_limit,_actor(request))

@router.get("/{camera_id}/jobs")
def jobs(centre_id:str,camera_id:str,request:Request):
    _centre(request,centre_id)
    return {"jobs":db.list_jobs(centre_id,camera_id)}

@router.post("/{camera_id}/jobs/{job_id}/cancel")
def cancel(centre_id:str,camera_id:str,job_id:str,request:Request):
    _centre(request,centre_id,True)
    return db.cancel_job(centre_id,camera_id,job_id,_actor(request))

@router.get("/{camera_id}/observations")
def observations(centre_id:str,camera_id:str,request:Request):
    _centre(request,centre_id)
    return {"observations":db.observations(centre_id,camera_id)}

@router.post("/{camera_id}/observations/{observation_id}/review")
def review(centre_id:str,camera_id:str,observation_id:str,
           body:ReviewIn,request:Request):
    _centre(request,centre_id,True)
    if body.decision not in {"needs_followup","not_actionable","reviewed"}:
        raise HTTPException(422,"Unsupported review decision")
    return db.review_observation(centre_id,camera_id,observation_id,
                                 body.decision,body.note.strip(),_actor(request))

@router.get("/{camera_id}/audit")
def audit(centre_id:str,camera_id:str,request:Request):
    _centre(request,centre_id)
    return {"events":db.audit_events(centre_id,camera_id)}
