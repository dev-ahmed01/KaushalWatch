from __future__ import annotations
from pathlib import Path
import importlib.util
import os
import json
import tempfile
import cv2
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.models import ReviewRequest, EdgeSyncRequest
from app.services.case_store import CaseStore
from app.services.infrastructure import aggregate_cached_observations, compare_manifest
from app.services.infrastructure_pipeline import InfrastructureCompliancePipeline
from app.services.compliance_cases import build_infrastructure_case
from app.services.operability import apparent_motion_state
from app.services.video_pipeline import VideoCompliancePipeline
from app.services.practical_activity_pipeline import PracticalActivityPipeline
from app.services.offline_queue import json_payload_bytes
from app.services.demo_assets import load_demo_manifest_and_cache, build_compliant_demo_cache

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
EVIDENCE = DATA / "evidence"
STORE = CaseStore(DATA / "cases.json")
PIPELINE = VideoCompliancePipeline(EVIDENCE, DATA / "evidence_index.json")
PRACTICAL_PIPELINE = PracticalActivityPipeline(EVIDENCE, DATA / "evidence_index.json")
DEFAULT_WORK_ZONES = ROOT / "backend" / "app" / "demo_configs" / "work_zones.json"
INFRA_PIPELINE = InfrastructureCompliancePipeline(EVIDENCE, DATA / "evidence_index.json", privacy_detector=PIPELINE.detector)

app = FastAPI(title="KaushalWatch API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
EVIDENCE.mkdir(parents=True, exist_ok=True)
app.mount("/evidence", StaticFiles(directory=str(EVIDENCE)), name="evidence")

SUPPORTED_VIDEO_SUFFIXES = {".mp4", ".avi", ".mov", ".mkv", ".mpeg", ".mpg"}


def _materialize_video_upload(file: UploadFile) -> Path:
    filename = file.filename or "video.mp4"
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_VIDEO_SUFFIXES:
        allowed = ", ".join(sorted(SUPPORTED_VIDEO_SUFFIXES))
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported video format '{suffix or 'none'}'. Use one of: {allowed}",
        )

    max_upload_mb = int(os.getenv("KAUSHALWATCH_MAX_UPLOAD_MB", "500"))
    max_bytes = max_upload_mb * 1024 * 1024
    total = 0

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp_path = Path(tmp.name)
        try:
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=(
                            f"Video exceeds the {max_upload_mb} MB demo upload limit. "
                            "Trim the clip before analysis."
                        ),
                    )
                tmp.write(chunk)
        except Exception:
            tmp.close()
            tmp_path.unlink(missing_ok=True)
            raise

    if total == 0:
        tmp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Uploaded video is empty")

    return tmp_path


@app.get("/api/health")
def health():
    return {"ok": True, "service": "kaushalwatch-api", "prototype": True}


@app.get("/api/runtime-readiness")
def runtime_readiness():
    detector = PIPELINE.detector.info

    zones_ready = DEFAULT_WORK_ZONES.exists()
    yolo_available = importlib.util.find_spec("ultralytics") is not None
    practical_ready = zones_ready and yolo_available

    try:
        load_demo_manifest_and_cache()
        infrastructure_ready = True
        infrastructure_message = (
            "Stage-safe infrastructure manifest and cached detector telemetry are available."
        )
    except (FileNotFoundError, ValueError) as exc:
        infrastructure_ready = False
        infrastructure_message = f"Infrastructure demo assets unavailable: {exc}"

    if practical_ready:
        practical_message = "YOLO runtime and bundled work-zone profiles are available."
    elif not yolo_available and not zones_ready:
        practical_message = (
            "Practical-work runtime unavailable: install YOLO demo dependencies and "
            "restore bundled work-zone profiles."
        )
    elif not yolo_available:
        practical_message = (
            "Practical-work runtime unavailable: install backend/requirements-yolo-demo.txt."
        )
    else:
        practical_message = "Practical-work runtime unavailable: bundled work-zone profiles are missing."

    return {
        "attendance": {
            "ready": bool(detector.authoritative),
            "backend": detector.backend,
            "mode": detector.mode,
            "message": detector.message,
        },
        "practical_work": {
            "ready": practical_ready,
            "backend": "yolo11",
            "default_zone_profiles": ["default", "authorized", "unauthorized"],
            "message": practical_message,
        },
        "infrastructure": {
            "ready": infrastructure_ready,
            "mode": "stage_safe_cached_adapter",
            "message": infrastructure_message,
        },
        "evidence": {
            "ready": EVIDENCE.exists(),
            "privacy_note": (
                "Person regions are blurred where a primary person detector is available; "
                "human review remains required."
            ),
        },
    }


@app.get("/api/dashboard")
def dashboard():
    cases = STORE.list()
    edge_events_path = DATA / "edge_events.json"
    edge_events = json.loads(edge_events_path.read_text()) if edge_events_path.exists() else []
    pending_statuses = {"open", "under_review", "virtual_verification"}
    pending_cases = [c for c in cases if c.status.value in pending_statuses]
    resolved_cases = [c for c in cases if c.status.value not in pending_statuses]
    return {
        "banner": "Prototype — Simulated Operational Data",
        "centres_monitored": 4,
        "open_cases": len(pending_cases),
        "resolved_cases": len(resolved_cases),
        "camera_issues": sum(
            c.case_type == "camera_integrity" and c.status.value in pending_statuses
            for c in cases
        ),
        "synced_edge_events": len(edge_events),
        "edge_sync_state": "idle" if not edge_events else "synced",
        "pending_cases": [c.model_dump(mode="json") for c in pending_cases[-20:]],
        "resolved_case_history": [c.model_dump(mode="json") for c in resolved_cases[-20:]],
        "cases": [c.model_dump(mode="json") for c in cases[-40:]],
    }


@app.post("/api/process-video")
def process_video(
    file: UploadFile = File(...),
    reported_attendance: int = Form(...),
    centre_id: str = Form("DEMO-KA-104"),
    batch_id: str = Form("ELEC-DEMO-01"),
    camera_id: str = Form("LAB-CAM-01"),
):
    tmp_path = _materialize_video_upload(file)
    try:
        result = PIPELINE.run(tmp_path, reported_attendance, centre_id, batch_id, camera_id=camera_id)
        if result.case:
            STORE.save(result.case)
        return result.model_dump(mode="json")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        tmp_path.unlink(missing_ok=True)


@app.post("/api/process-practical-activity")
def process_practical_activity(
    file: UploadFile = File(...),
    zones_json: str | None = Form(None),
    authorization: str = Form("unknown"),
    zone_profile: str = Form("default"),
    centre_id: str = Form("DEMO-KA-104"),
    batch_id: str = Form("ELEC-DEMO-01"),
    camera_id: str = Form("LAB-CAM-03"),
):
    """Analyse stable anonymous worker presence + worker-centric motion in work cells.

    Authorization is supplied externally. Vision does not infer identity,
    authorization, skill quality, or exact task semantics.
    """
    source_text = zones_json
    if not source_text:
        if not DEFAULT_WORK_ZONES.exists():
            raise HTTPException(
                status_code=500,
                detail="Bundled practical-work zone configuration is missing",
            )
        source_text = DEFAULT_WORK_ZONES.read_text(encoding="utf-8")

    try:
        parsed = json.loads(source_text)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid work-zone JSON") from exc

    selected_profile = zone_profile or "default"
    zone_reference_size = None
    if isinstance(parsed, dict):
        reference = parsed.get("_reference")
        if isinstance(reference, dict):
            try:
                reference_width = int(reference["width"])
                reference_height = int(reference["height"])
            except (KeyError, TypeError, ValueError) as exc:
                raise HTTPException(
                    status_code=400,
                    detail="Work-zone _reference requires integer width and height",
                ) from exc
            zone_reference_size = (reference_width, reference_height)

    if isinstance(parsed, dict) and isinstance(parsed.get("zones"), list):
        zones = parsed["zones"]
    elif (
        isinstance(parsed, dict)
        and isinstance(parsed.get(selected_profile), list)
    ):
        zones = parsed[selected_profile]
    elif isinstance(parsed, list):
        zones = parsed
    else:
        raise HTTPException(
            status_code=400,
            detail=(
                "Work-zone JSON must be a list, contain a 'zones' list, or contain "
                f"a list matching profile '{selected_profile}'"
            ),
        )

    tmp_path = _materialize_video_upload(file)

    try:
        result = PRACTICAL_PIPELINE.run(
            video_path=tmp_path,
            zones=zones,
            authorization=authorization,
            centre_id=centre_id,
            batch_id=batch_id,
            camera_id=camera_id,
            zone_reference_size=zone_reference_size,
        )
        if result.case:
            STORE.save(result.case)
        return result.model_dump(mode="json")
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        tmp_path.unlink(missing_ok=True)


@app.get("/api/cases")
def list_cases():
    return [c.model_dump(mode="json") for c in STORE.list()]


@app.get("/api/cases/{case_id}/evidence-pack")
def get_evidence_pack(case_id: str):
    case = STORE.get(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return {
        "prototype": True,
        "case": case.model_dump(mode="json"),
        "integrity": [
            {
                "evidence_id": e.evidence_id,
                "sha256": e.sha256,
                "perceptual_hash": e.perceptual_hash,
                "possible_duplicate": e.duplicate_of is not None,
                "duplicate_of": e.duplicate_of,
            }
            for e in case.evidence
        ],
        "decision_policy": (
            "AI evidence supports human review only; no automatic penalty or final compliance "
            "decision is issued by this prototype."
        ),
    }


@app.post("/api/cases/{case_id}/review")
def review_case(case_id: str, request: ReviewRequest):
    terminal_actions = {"confirmed", "false_positive", "resolved"}
    note = (request.note or "").strip()
    if request.action.value in terminal_actions and not note:
        raise HTTPException(
            status_code=422,
            detail="A review note is required for a final case decision",
        )

    try:
        case = STORE.update_status(
            case_id,
            request.action,
            note=note or None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case.model_dump(mode="json")


@app.get("/api/demo/infrastructure")
def infrastructure_demo():
    try:
        manifest, rows = load_demo_manifest_and_cache()
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    observed = aggregate_cached_observations(rows)
    return {
        "banner": "Prototype — cached detections on a demo configuration, not official live compliance data",
        "job_role": manifest["job_role"],
        "items": compare_manifest(manifest, observed),
    }




@app.post("/api/process-infrastructure-video")
def process_infrastructure_video(
    file: UploadFile = File(...),
    centre_id: str = Form("DEMO-KA-104"),
    batch_id: str = Form("ELEC-DEMO-01"),
    camera_id: str = Form("LAB-CAM-02"),
    demo_profile: str = Form("compliant"),
    operability_item_id: str | None = Form("drill_machine"),
    roi_x1: int | None = Form(None),
    roi_y1: int | None = Form(None),
    roi_x2: int | None = Form(None),
    roi_y2: int | None = Form(None),
):
    """Stage-safe infrastructure pipeline using the demo manifest + cached detections.

    The uploaded video supplies actual evidence and optional operability frames.
    Equipment observations are currently sourced from the cached detector adapter;
    GroundingDINO can replace that adapter without changing the case workflow.
    """
    try:
        manifest, rows = load_demo_manifest_and_cache()
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if demo_profile == "compliant":
        rows = build_compliant_demo_cache(manifest)
    elif demo_profile != "discrepancy":
        raise HTTPException(
            status_code=400,
            detail="demo_profile must be 'compliant' or 'discrepancy'",
        )

    observed_preview = aggregate_cached_observations(rows)
    preview_items = compare_manifest(manifest, observed_preview)

    roi_values = (roi_x1, roi_y1, roi_x2, roi_y2)
    if any(v is not None for v in roi_values) and not all(v is not None for v in roi_values):
        raise HTTPException(status_code=400, detail="Provide all ROI coordinates or none")
    roi = tuple(int(v) for v in roi_values) if all(v is not None for v in roi_values) else None

    tmp_path = _materialize_video_upload(file)

    try:
        case = INFRA_PIPELINE.run(
            video_path=tmp_path,
            manifest=manifest,
            detection_rows=rows,
            centre_id=centre_id,
            batch_id=batch_id,
            camera_id=camera_id,
            operability_item_id=operability_item_id if roi else None,
            operability_roi=roi,
        )
        if not case:
            return {
                "created": False,
                "banner": (
                    "Prototype — explicit compliant demo profile; no persistent "
                    "visual manifest exception"
                    if demo_profile == "compliant"
                    else "Prototype — cached equipment detections; no persistent visual manifest exception"
                ),
                "demo_profile": demo_profile,
                "items": preview_items,
            }
        STORE.save(case)
        return {
            "created": True,
            "banner": (
                "Prototype — uploaded video evidence with cached equipment detections; "
                "not official live compliance data"
            ),
            "demo_profile": demo_profile,
            "items": preview_items,
            "case": case.model_dump(mode="json"),
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        tmp_path.unlink(missing_ok=True)


@app.post("/api/operability-check")
def operability_check(
    file: UploadFile = File(...),
    x1: int = Form(...), y1: int = Form(...), x2: int = Form(...), y2: int = Form(...),
):
    tmp_path = _materialize_video_upload(file)
    frames = []
    cap = cv2.VideoCapture(str(tmp_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    step = max(1, int(fps / 2))
    i = 0
    try:
        while len(frames) < 30:
            ok, frame = cap.read()
            if not ok:
                break
            if i % step == 0:
                frames.append(frame)
            i += 1
        state, activity_score = apparent_motion_state(frames, (x1, y1, x2, y2))
        return {
            "state": state,
            "activity_score": round(activity_score, 4),
            "interpretation": "Visual activity proxy only; not a mechanical/electrical health diagnosis.",
            "frames_sampled": len(frames),
        }
    finally:
        cap.release()
        tmp_path.unlink(missing_ok=True)



@app.post("/api/demo/infrastructure/create-case")
def create_demo_infrastructure_case(
    centre_id: str = Form("DEMO-KA-104"),
    batch_id: str = Form("ELEC-DEMO-01"),
):
    try:
        manifest, rows = load_demo_manifest_and_cache()
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    observed = aggregate_cached_observations(rows)
    results = compare_manifest(manifest, observed)
    case = build_infrastructure_case(
        centre_id=centre_id,
        batch_id=batch_id,
        job_role=manifest["job_role"],
        results=results,
    )
    if not case:
        return {
            "created": False,
            "message": "No persistent demo infrastructure exception found.",
            "items": results,
        }
    STORE.save(case)
    return {
        "created": True,
        "banner": "Prototype — case derived from cached/simulated equipment detections",
        "case": case.model_dump(mode="json"),
    }



@app.post("/api/edge/sync")
def edge_sync(request: EdgeSyncRequest):
    """Prototype cloud-side receiver for queued edge telemetry; raw video is not required."""
    events_path = DATA / "edge_events.json"
    rows = json.loads(events_path.read_text()) if events_path.exists() else []
    accepted = []
    existing = {row.get("event_id") for row in rows}
    for event in request.events:
        event_id = event.get("event_id")
        if not event_id or event_id in existing:
            continue
        rows.append(event)
        existing.add(event_id)
        accepted.append(event_id)
    events_path.write_text(json.dumps(rows, indent=2))
    return {
        "accepted_event_ids": accepted,
        "accepted_count": len(accepted),
        "received_payload_bytes": json_payload_bytes(request.events),
        "raw_video_required": False,
    }
