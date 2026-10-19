"""Read-only Camera Trust pilot deployment preflight.

This does not deploy, download private media or establish physical camera health.
Use the same environment as the target API/worker. Never print secret values.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"backend"))

def check_environment(component:str, env:dict[str,str], *, probe_db:bool=False) -> dict:
    checks={}
    def check(name:str, okay:bool):
        checks[name]="PASS" if okay else "BLOCKED"
    protected=env.get("KAUSHALWATCH_ENV","").strip().lower() in {"pilot","production","prod"}
    check("protected_environment",protected)
    if component in ("api","worker","full"):
        try:
            from app.services.demo_network import provisioned_centres
            configured=provisioned_centres()
            centre_ok=bool(configured) and all(not c["centre_id"].startswith("DEMO-")
                                               for c in configured) if protected else bool(configured)
        except Exception:
            centre_ok=False
        check("real_centre_registry_provisioned",centre_ok)
    check("postgres_selected",env.get("KAUSHALWATCH_STORAGE_BACKEND","")=="postgres")
    if component in ("api","full"):
        check("private_evidence_selected",env.get("KAUSHALWATCH_EVIDENCE_BACKEND","")=="s3")
    dsn=env.get("KAUSHALWATCH_DATABASE_URL","")
    check("postgres_dsn_configured",dsn.startswith(("postgres://","postgresql://")))
    if component in ("api","full"):
        check("oidc_officer_identity_selected",
              env.get("KAUSHALWATCH_REVIEW_AUTH_MODE","")=="oidc")
        check("oidc_scoped_subject_grants_configured",
              bool(env.get("KAUSHALWATCH_OIDC_GRANTS_JSON","").strip()))
        check("evidence_storage_configured",
              bool(env.get("KAUSHALWATCH_EVIDENCE_S3_BUCKET","") and
                   env.get("KAUSHALWATCH_EVIDENCE_S3_REGION","") and
                   env.get("KAUSHALWATCH_EVIDENCE_KMS_KEY_ID","") and
                   not env.get("KAUSHALWATCH_EVIDENCE_S3_ENDPOINT_URL","")))
    if component in ("web","full"):
        check("protected_web_session",
              env.get("KAUSHALWATCH_WEB_AUTH_MODE","")=="protected")
        check("same_origin_proxy",
              env.get("NEXT_PUBLIC_KAUSHALWATCH_SECURE_PROXY","")=="true")
        check("backend_private_address",
              bool(env.get("KAUSHALWATCH_API_INTERNAL_URL","").strip()))
    if component in ("worker","full"):
        from camera_trust_workstation.kwtrust.drive_sync import load_manifest
        from app.services.camera_sources import permitted_aliases
        path=env.get("KAUSHALWATCH_CAMERA_DRIVE_MANIFEST","")
        manifest=[]
        if path and Path(path).is_file():
            try:manifest=load_manifest(Path(path))
            except (ValueError,OSError,KeyError,json.JSONDecodeError):pass
        check("private_sha_pinned_manifest",
              bool(manifest) and all(isinstance(x.get("sha256"),str) and
                                     len(x["sha256"])==64 for x in manifest))
        if manifest:
            # No actual source ID or name is ever returned to caller.
            try:
                from app.services.demo_network import provisioned_centres
                active=sum(len(permitted_aliases(c["centre_id"],manifest,
                            env.get("KAUSHALWATCH_CAMERA_SOURCE_GRANTS_JSON","")))
                           for c in provisioned_centres())
                grants_ok=active>0
            except Exception:grants_ok=False
        else:grants_ok=False
        check("centre_source_grants",grants_ok)
        token=env.get("KAUSHALWATCH_CAMERA_DRIVE_TOKEN","")
        check("oauth_token_or_adc_available",
              (bool(token) and Path(token).is_file()) or
              bool(env.get("GOOGLE_APPLICATION_CREDENTIALS","") and
                   Path(env["GOOGLE_APPLICATION_CREDENTIALS"]).is_file()))
        media=env.get("KAUSHALWATCH_CAMERA_MEDIA_DIR","")
        check("private_media_cache_is_configured",bool(media) and
              Path(media).exists() and os.access(media,os.W_OK))
        checks["external_custody_and_field_accuracy"]="NOT_VERIFIED"
    if probe_db:
        if dsn.startswith(("postgres://","postgresql://")):
            try:
                from app.services.postgres_store import connection
                with connection() as db:
                    rows=db.execute("""SELECT
                      to_regclass('kw_camera_registry') AS registry,
                      to_regclass('kw_camera_jobs') AS jobs,
                      to_regclass('kw_camera_references') AS refs,
                      to_regclass('kw_camera_audit') AS audit""").fetchone()
                check("postgres_camera_schema_v3",all(rows.values()))
            except Exception:
                check("postgres_camera_schema_v3",False)
        else:check("postgres_camera_schema_v3",False)
    else:checks["postgres_camera_schema_v3"]="NOT_PROBED"
    blockers=[key for key,state in checks.items() if state=="BLOCKED"]
    # NOT_VERIFIED and NOT_PROBED prevent any statement of site acceptance.
    return {"schema":"KW_CAMERA_DEPLOYMENT_PREFLIGHT_V1","component":component,
            "shadow_software_configuration":
              "CONFIG_CHECKS_PASS" if not blockers else "BLOCKED",
            "safe_to_enable_autonomous_enforcement":False,
            "deployed_and_operational_at_real_site":False,
            "physical_camera_health":"UNKNOWN",
            "checks":checks,"blocking_check_names":blockers,
            "secrets_or_source_identifiers_emitted":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--component",choices=("api","worker","web","full"),default="full")
    p.add_argument("--probe-database",action="store_true",
                   help="Read-only query of schema existence using configured DSN")
    p.add_argument("--output",type=Path)
    args=p.parse_args()
    report=check_environment(args.component,dict(os.environ),probe_db=args.probe_database)
    blob=json.dumps(report,indent=2,sort_keys=True)+"\n"
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        fd=os.open(args.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,"w",encoding="utf-8") as out:out.write(blob)
    else:print(blob,end="")
    raise SystemExit(0 if report["shadow_software_configuration"]=="CONFIG_CHECKS_PASS"
                     and (not args.probe_database or report["checks"]["postgres_camera_schema_v3"]=="PASS")
                     else 2)
if __name__=="__main__":main()
