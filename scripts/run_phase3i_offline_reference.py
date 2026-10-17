#!/usr/bin/env python3
"""OFFLINE ONLY: replay frozen reference against pre-hashed local UHCTD clips.

Requires staging token-mode officer access FROM A TRUSTED PRIVATE ENVIRONMENT.
The secret comes from an environment variable, never a command-line argument.
OIDC approval requires a separately verified server-side worker integration;
do not synthesize arbitrary principal identities for command line use.

The run saves aggregate numeric JSON only. It cannot alter camera baselines,
attendance, sanctions, case state or production services.
"""
from __future__ import annotations

import argparse
import hmac
import json
import os
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"backend"))

from app.services.review_access import _configuration  # noqa: E402
from app.services.officer_permissions import configured_principals  # noqa: E402
from app.services.camera_reference_offline_session import OfflineApprovedReferenceSession  # noqa: E402
from app.services.camera_reference_offline_benchmark import evaluate_recording  # noqa: E402


def authenticated_offline_principal():
    # Staging token mode is only a prototype; production OIDC tokens should be
    # processed by the actual authenticated server endpoint/worker, not this CLI.
    if (os.getenv("KAUSHALWATCH_ENV","").lower() != "staging"
            or os.getenv("KAUSHALWATCH_CAMERA_REFERENCE_WORKFLOW") != "shadow_artifact"
            or os.getenv("KAUSHALWATCH_STORAGE_BACKEND") != "postgres"
            or os.getenv("KAUSHALWATCH_REVIEW_AUTH_MODE") != "token"):
        raise RuntimeError("Offline CLI requires explicit protected staging token mode")
    token=os.getenv("KAUSHALWATCH_PHASE3I_OFFLINE_TOKEN","")
    if not token or len(token)>1024:
        raise RuntimeError("Private Phase 3I token env var is required")
    mode,tokens=_configuration()
    if mode!="token":
        raise RuntimeError("This CLI does not support OIDC; use verified server worker instead")
    actor=None
    for candidate,expected in tokens.items():
        if hmac.compare_digest(token,expected):
            actor=candidate
    if actor is None:
        raise RuntimeError("Offline reviewer token is not authorized")
    officer=configured_principals().get(actor)
    if officer is None or officer.role!="network_admin":
        raise RuntimeError("Offline playback requires network administrator permission")
    return officer


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest",type=Path,required=True,
                        help="JSON centre, camera, revision, source-video/label paths and hashes")
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--sample-seconds",type=float,default=1.0)
    parser.add_argument("--preview-seconds",type=float)
    args=parser.parse_args()
    if args.out.suffix.lower()!=".json":
        parser.error("Output must be a local JSON file")
    if args.out.exists():
        parser.error("Refuse to overwrite prior evaluation results")
    if not args.manifest.is_file():
        parser.error("Offline manifest must exist")
    data=json.loads(args.manifest.read_text(encoding="utf-8"))
    fields={
        "centre_id","camera_id","revision","video","annotations",
        "video_sha256","annotations_sha256",
    }
    if not isinstance(data,dict) or set(data)!=fields:
        parser.error(f"Manifest must contain exactly: {', '.join(sorted(fields))}")
    if type(data["revision"]) is not int or data["revision"]<=0:
        parser.error("Manifest reference revision must be positive integer")
    if any(not isinstance(data[k],str) for k in fields-{"revision"}):
        parser.error("Manifest paths, IDs and hashes must be strings")
    officer=authenticated_offline_principal()
    session=OfflineApprovedReferenceSession.open(
        principal=officer,centre_id=data["centre_id"],
        camera_id=data["camera_id"],revision=data["revision"],
    )
    try:
        outcome=evaluate_recording(
            video=Path(data["video"]),labels=Path(data["annotations"]),
            session=session,
            expected_video_sha256=data["video_sha256"],
            expected_labels_sha256=data["annotations_sha256"],
            sample_seconds=args.sample_seconds,
            preview_seconds=args.preview_seconds,
        )
    finally:
        session.close()
    args.out.parent.mkdir(parents=True,exist_ok=True)
    # Never store partially evaluated "success" reports.
    with args.out.open("x",encoding="utf-8") as target:
        json.dump(outcome,target,indent=2,sort_keys=True)
        target.write("\n")
    print(json.dumps({
        "status":outcome["status"],"qualified":False,
        "normal_review_fraction":outcome["normal_review_fraction"],
        "normal_review_episodes_per_hour":outcome["new_normal_review_episodes_per_normal_hour"],
        "moved":outcome["per_class"]["moved"],
        "report":str(args.out.resolve()),
    },indent=2))


if __name__=="__main__":
    main()
