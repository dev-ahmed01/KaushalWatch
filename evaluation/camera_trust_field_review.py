"""Externally signed field-review dossier validator; never enables enforcement.

A review-ready dossier is not proof of physical custody, nor a production
activation. Three trusted, distinct external public keys must attest exactly
the same frozen policy and measurements. Only an independent authority can
decide whether submitted measurements genuinely represent physical events.
"""
from __future__ import annotations
import base64
from datetime import datetime, timezone
import hashlib
import json
import math
import re

SCHEMA="KW_CAMERA_FIELD_REVIEW_V1"
REQUIRED_ROLES=("source_custodian","independent_adjudicator","release_authority")
CLASSES=("covered","defocused","moved")
HEX=re.compile(r"^[0-9a-f]{64}$")
ID=re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}$")

class FieldReviewError(ValueError):pass

def require(condition:bool,detail:str)->None:
    if not condition:raise FieldReviewError(detail)

def canonical(value)->bytes:
    return json.dumps(value,sort_keys=True,separators=(",",":"),
                      ensure_ascii=True,allow_nan=False).encode()

def timestamp(value)->datetime:
    try:
        dt=datetime.fromisoformat(value.replace("Z","+00:00"))
        require(dt.tzinfo is not None,"Field date must have timezone")
        return dt.astimezone(timezone.utc)
    except (ValueError,AttributeError,TypeError) as exc:
        raise FieldReviewError("Invalid field timestamp") from exc

def number(v,name:str,*,minimum:float=0,max_value:float=1e9)->float:
    require(type(v) in (int,float) and math.isfinite(v) and
            minimum<=v<=max_value,f"Invalid field measurement: {name}")
    return float(v)

def signed_dossier(bundle:dict, trusted_keys:dict) -> dict:
    """Return reviewed numeric metrics only after separately trusted signatures."""
    require(isinstance(bundle,dict) and bundle.get("schema")==SCHEMA,
            "Unknown field review schema")
    require(set(bundle)=={"schema","policy","measurements","signatures"},
            "Field dossier has extra/missing top-level fields")
    require(isinstance(trusted_keys,dict) and
            set(trusted_keys)==set(REQUIRED_ROLES),"Three external trust anchors required")
    require(isinstance(bundle["signatures"],dict) and
            set(bundle["signatures"])==set(REQUIRED_ROLES),"Three role signatures required")
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.exceptions import InvalidSignature
    except ImportError as exc:
        raise FieldReviewError("Cryptography support unavailable") from exc
    message=b"KW_CAMERA_FIELD_REVIEW_V1\x00"+canonical({
        "schema":bundle["schema"],"policy":bundle["policy"],
        "measurements":bundle["measurements"]})
    seen=set()
    for role in REQUIRED_ROLES:
        try:
            pub=base64.b64decode(trusted_keys[role],validate=True)
            sig=base64.b64decode(bundle["signatures"][role],validate=True)
            require(len(pub)==32 and len(sig)==64,"Invalid Ed25519 public key or signature")
            require(pub not in seen,"Field reviewer roles must have distinct keys")
            seen.add(pub)
            Ed25519PublicKey.from_public_bytes(pub).verify(sig,message)
        except (ValueError,TypeError,KeyError,InvalidSignature) as exc:
            raise FieldReviewError("External field signature invalid for "+role) from exc
    policy=bundle["policy"]
    metrics=bundle["measurements"]
    require(isinstance(policy,dict) and isinstance(metrics,dict),
            "Policy and measurements must be objects")
    require(set(policy)=={"policy_sha256","policy_frozen_at","max_false_alerts_per_100_camera_hours",
                         "max_p95_latency_seconds","min_normal_camera_hours",
                         "min_sites","min_cameras","min_events_per_class",
                         "min_event_recall_by_class"},
            "Incomplete preregistered policy")
    require(isinstance(policy["policy_sha256"],str) and
            HEX.fullmatch(policy["policy_sha256"]) is not None,
            "Policy digest must be SHA-256")
    frozen=timestamp(policy["policy_frozen_at"])
    require(set(metrics)=={"started_at","ended_at","normal_camera_hours",
                           "false_alert_episodes","events_by_class",
                           "latencies_seconds","sites","cameras",
                           "source_custody_attested","blind_independent_adjudication",
                           "no_automatic_enforcement","external_annotation_reference_sha256"},
            "Field measurements incomplete")
    started=timestamp(metrics["started_at"]);ended=timestamp(metrics["ended_at"])
    require(frozen<started<ended,"Frozen policy must precede field observation period")
    require(isinstance(metrics["external_annotation_reference_sha256"],str) and
            HEX.fullmatch(metrics["external_annotation_reference_sha256"]) is not None,
            "External annotations must have pinned digest")
    require(metrics["source_custody_attested"] is True and
            metrics["blind_independent_adjudication"] is True and
            metrics["no_automatic_enforcement"] is True,
            "Field custody/blinding/shadow declarations required")
    sites=metrics["sites"];cameras=metrics["cameras"]
    require(isinstance(sites,list) and isinstance(cameras,list) and
            all(isinstance(x,str) and ID.fullmatch(x) for x in sites+cameras) and
            len(sites)==len(set(sites)) and len(cameras)==len(set(cameras)),
            "Duplicate or invalid field site/camera IDs")
    require(type(policy["min_sites"]) is int and policy["min_sites"]>=2 and
            type(policy["min_cameras"]) is int and policy["min_cameras"]>=3 and
            type(policy["min_events_per_class"]) is int and
            policy["min_events_per_class"]>=2,
            "Policy minimum exposure is too weak for field-review automation")
    normal=number(metrics["normal_camera_hours"],"normal_camera_hours",minimum=0)
    false=metrics["false_alert_episodes"]
    require(type(false) is int and 0<=false<=1_000_000,
            "False alerts must be a count of adjudicated episodes")
    require(normal>=0 and normal<=1000000,"Invalid normal-hours exposure")
    require(isinstance(metrics["events_by_class"],dict) and
            set(metrics["events_by_class"])==set(CLASSES),"All classes required")
    recall={}
    for cls in CLASSES:
        row=metrics["events_by_class"][cls]
        require(isinstance(row,dict) and set(row)=={"events","detected"},
                "Event class must include events and detections")
        events=row["events"];det=row["detected"]
        require(type(events) is int and type(det) is int and
                0<=det<=events<=1_000_000,"Invalid field event counts")
        recall[cls]=round(det/events,6) if events else None
    lat=metrics["latencies_seconds"]
    require(isinstance(lat,list) and len(lat)<=100000 and
            len(lat)==sum(metrics["events_by_class"][c]["detected"] for c in CLASSES),
            "Latency samples must match independent true alert detections")
    values=sorted(number(v,"latency",minimum=0,max_value=86400) for v in lat)
    p95=values[max(0,math.ceil(.95*len(values))-1)] if values else None
    max_nuisance=number(policy["max_false_alerts_per_100_camera_hours"],
                        "max_false_alerts_per_100_camera_hours",max_value=1000)
    max_latency=number(policy["max_p95_latency_seconds"],
                       "max_p95_latency_seconds",minimum=.001,max_value=86400)
    min_hours=number(policy["min_normal_camera_hours"],
                     "min_normal_camera_hours",minimum=24,max_value=1000000)
    cutoffs=policy["min_event_recall_by_class"]
    require(isinstance(cutoffs,dict) and set(cutoffs)==set(CLASSES),
            "Preregistered recall policy missing class")
    for value in cutoffs.values():
        require(type(value) in (int,float) and math.isfinite(value) and 0<value<=1,
                "Invalid preregistered sensitivity threshold")
    nuisance=100*false/normal if normal else None
    results={
        "site_coverage":len(sites)>=policy["min_sites"],
        "camera_coverage":len(cameras)>=policy["min_cameras"],
        "normal_exposure":normal>=min_hours,
        "nuisance_episode_rate":nuisance is not None and nuisance<=max_nuisance,
        "p95_operator_alert_latency":p95 is not None and p95<=max_latency,
    }
    for cls in CLASSES:
        results["independent_"+cls+"_recall"]=(
            metrics["events_by_class"][cls]["events"]>=policy["min_events_per_class"] and
            recall[cls] is not None and recall[cls]>=cutoffs[cls])
    ready=all(results.values())
    return {"schema":"KW_CAMERA_FIELD_REVIEW_RESULT_V1",
            "external_attestations_verified":True,
            "dossier_sha256":hashlib.sha256(message).hexdigest(),
            "policy_sha256":policy["policy_sha256"],
            "normal_camera_hours":round(normal,3),
            "false_alert_episodes":false,
            "false_alerts_per_100_camera_hours":round(nuisance,6) if nuisance is not None else None,
            "p95_latency_seconds":p95,
            "class_event_recall":recall,"checks":results,
            "manual_review_readiness":"EVIDENCE_READY_FOR_INDEPENDENT_MANUAL_REVIEW"
              if ready else "EVIDENCE_BELOW_SIGNED_POLICY",
            "autonomous_enforcement_authorized":False,
            "physical_truth_cryptographically_proven":False,
            "deployed_at_real_site_confirmed":False}

def blocked() -> dict:
    return {"schema":"KW_CAMERA_FIELD_REVIEW_RESULT_V1",
            "manual_review_readiness":"BLOCKED_NO_EXTERNALLY_SIGNED_FIELD_DOSSIER",
            "autonomous_enforcement_authorized":False,
            "physical_truth_cryptographically_proven":False}
