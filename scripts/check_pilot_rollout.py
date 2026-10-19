"""Read-only, fail-closed pilot acceptance gate; no media or officer actions.

A successful software preflight can never approve the physical camera,
IdP MFA, private evidence custody, real deployment or autonomous enforcement.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"backend"))
from scripts.check_camera_trust_deployment import check_environment
from scripts.check_protected_staging import run_check
from scripts.pilot_release_lock import load_lock, valid_lock
from scripts.check_private_storage_cloud import evaluate as inspect_private_storage
from evaluation.camera_trust_field_review import FieldReviewError,signed_dossier

SCHEMA="KW_PILOT_ACCEPTANCE_V1"
FIELD_READY="EVIDENCE_READY_FOR_INDEPENDENT_MANUAL_REVIEW"

def load_private(path:Path)->dict:
    if not path.is_file() or not 0<path.stat().st_size<=16*1024*1024:
        raise ValueError("Field document missing or unsafe")
    value=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value,dict):
        raise ValueError("Field document must be a JSON object")
    return value

def evaluate(env:dict[str,str],*,api:str|None=None,web:str|None=None,
             probe_db:bool=False,field_bundle:dict|None=None,
             trusted_public_keys:dict|None=None,
             release_lock:dict|None=None,expected_release_commit:str|None=None,
             probe_private_storage_cloud:bool=False)->dict[str,Any]:
    config=check_environment("full",env,probe_db=probe_db)
    checks=dict(config["checks"])
    if not probe_private_storage_cloud:
        checks["private_storage_cloud_controls"]="NOT_PROBED"
    else:
        try:
            cloud=inspect_private_storage(env,probe=True)
            checks["private_storage_cloud_controls"]=(
                "PASS" if cloud.get("cloud_read_only_preflight")=="CHECKS_PASS"
                and cloud.get("probe_attempted") is True else "BLOCKED")
        except Exception:
            checks["private_storage_cloud_controls"]="BLOCKED"
    if release_lock is None and expected_release_commit is None:
        checks["immutable_release_lock_format"]="NOT_SUBMITTED"
    else:
        checks["immutable_release_lock_format"]=("PASS" if
            valid_lock(release_lock,expected_release_commit) else "BLOCKED")
    if api is None or web is None:
        checks["real_https_readiness"]="NOT_PROBED"
    else:
        try:
            result=run_check(api,web,synthetic=False)
            checks["real_https_readiness"]=("PASS" if result["passed"] and
                result["status"]=="public_preflight_passed" else "BLOCKED")
        except Exception:
            checks["real_https_readiness"]="BLOCKED"
    if field_bundle is None and trusted_public_keys is None:
        checks["signed_independent_field_dossier"]="NOT_SUBMITTED"
    elif not isinstance(field_bundle,dict) or not isinstance(trusted_public_keys,dict):
        checks["signed_independent_field_dossier"]="BLOCKED"
    else:
        try:
            result=signed_dossier(field_bundle,trusted_public_keys)
            checks["signed_independent_field_dossier"]=(
                "PASS" if result["manual_review_readiness"]==FIELD_READY
                else "BLOCKED")
        except (FieldReviewError,ValueError,TypeError,KeyError):
            checks["signed_independent_field_dossier"]="BLOCKED"
    # The component checker correctly leaves physical source custody
    # NOT_VERIFIED: that must still require an external operator sign-off,
    # but cannot make an otherwise passing *software* gate unreachable.
    # A real signed dossier is separately required below.
    technical={k:v for k,v in checks.items()
               if k!="external_custody_and_field_accuracy"}
    passing=all(x=="PASS" for x in technical.values())
    return {
        "schema":SCHEMA,
        "software_preflight":"CHECKS_PASS" if passing else "BLOCKED",
        "field_evidence":(FIELD_READY if checks["signed_independent_field_dossier"]=="PASS"
                          else "BLOCKED_OR_NOT_SUBMITTED"),
        "eligible_to_request_external_pilot_signoff":passing,
        "real_site_deployment_independently_verified":False,
        "external_operator_approval_recorded":False,
        "autonomous_enforcement_authorized":False,
        "pilot_activation":"BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
        "physical_camera_health":"UNKNOWN",
        "checks":checks,
        "blocking_check_names":sorted(k for k,v in technical.items() if v!="PASS"),
        "external_evidence_not_independently_verified":[
            "external_custody_and_field_accuracy",
            "site_authority_signoff",
        ],
        "operator_actions_remaining":[
            "Real IdP MFA and subject-revocation verification",
            "Independent private S3 IAM/KMS and source custody audit",
            "Operator read-only AWS bucket/KMS controls probe (does not test media)",
            "Verify actual registry and running image digests against source revision",
            "Verify rollback image compatibility with current PostgreSQL v3 schema",
            "Real infrastructure backup and disaster-recovery drill",
            "Independent physical camera evidence and operator sign-off",
        ],
        "secrets_or_source_identifiers_emitted":False,
    }

def write_receipt(path:Path,value:dict)->None:
    target=path.expanduser().resolve()
    if target==ROOT or ROOT in target.parents:
        raise ValueError("Private receipts must stay outside source repository")
    target.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"w",encoding="utf-8") as stream:
        json.dump(value,stream,indent=2,sort_keys=True,allow_nan=False)
        stream.write("\n");stream.flush();os.fsync(stream.fileno())

def main()->int:
    p=argparse.ArgumentParser(description="Read-only, non-authorizing real pilot gate")
    p.add_argument("--status",action="store_true")
    p.add_argument("--api")
    p.add_argument("--web")
    p.add_argument("--probe-database",action="store_true")
    p.add_argument("--probe-private-storage-cloud",action="store_true",
                   help="Opt-in read-only AWS bucket/KMS policy checks")
    p.add_argument("--field-bundle",type=Path)
    p.add_argument("--trusted-public-keys",type=Path)
    p.add_argument("--release-lock",type=Path)
    p.add_argument("--expected-release-commit")
    p.add_argument("--output",type=Path)
    args=p.parse_args()
    if args.status:
        if any((args.api,args.web,args.probe_database,args.probe_private_storage_cloud,args.field_bundle,args.trusted_public_keys,args.release_lock,args.expected_release_commit,args.output)):
            p.error("--status cannot be combined with other options")
        print(json.dumps(evaluate({}),indent=2))
        return 0
    if (args.api is None)!=(args.web is None):
        p.error("Supply both HTTPS API and web origins")
    if (args.field_bundle is None)!=(args.trusted_public_keys is None):
        p.error("Independent dossier requires separately trusted public keys")
    if (args.release_lock is None)!=(args.expected_release_commit is None):
        p.error("Supply both release lock and expected commit")
    try:
        receipt=evaluate(
            dict(os.environ),api=args.api,web=args.web,
            probe_db=args.probe_database,
            probe_private_storage_cloud=args.probe_private_storage_cloud,
            field_bundle=load_private(args.field_bundle) if args.field_bundle else None,
            trusted_public_keys=load_private(args.trusted_public_keys) if args.trusted_public_keys else None,
            release_lock=load_lock(args.release_lock) if args.release_lock else None,
            expected_release_commit=args.expected_release_commit)
        if args.output:write_receipt(args.output,receipt)
        else:print(json.dumps(receipt,indent=2))
    except (OSError,ValueError,json.JSONDecodeError):
        print(json.dumps({"schema":SCHEMA,"software_preflight":"BLOCKED",
            "pilot_activation":"BLOCKED_PENDING_EXTERNAL_AUTHORIZATION",
            "reason":"invalid_private_input_or_receipt_destination"}))
        return 2
    return 0 if receipt["eligible_to_request_external_pilot_signoff"] else 2

if __name__=="__main__":
    raise SystemExit(main())
