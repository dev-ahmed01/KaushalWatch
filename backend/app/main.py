from __future__ import annotations
from pathlib import Path
import json
import shutil
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
from app.services.demo_assets import load_demo_manifest_and_cache

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
EVIDENCE = DATA / "evidence"
STORE = CaseStore(DATA / "cases.json")
PIPELINE = VideoCompliancePipeline(EVIDENCE, DATA / "evidence_index.json")
PRACTICAL_PIPELINE = PracticalActivityPipeline(EVIDENCE, DATA / "evidence_index.json")
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


@app.get("/api/health")
def health():
    return {"ok": True, "service": "kaushalwatch-api", "prototype": True}


@app.get("/api/dashboard")
def dashboard():
    cases = STORE.list()
    edge_events_path = DATA / "edge_events.json"
    edge_events = json.loads(edge_events_path.read_text()) if edge_events_path.exists() else []
    return {
        "banner": "Prototype — Simulated Operational Data",
        "centres_monitored": 4,
        "open_cases": sum(c.status.value in {"open", "under_review", "virtual_verification"} for c in cases),
        "camera_issues": sum(c.case_type == "camera_integrity" and c.status.value != "resolved" for c in cases),
        "synced_edge_events": len(edge_events),
        "cases": [c.model_dump(mode="json") for c in cases[-20:]],
    }


@app.post("/api/process-video")
def process_video(
    file: UploadFile = File(...),
    reported_attendance: int = Form(...),
    centre_id: str = Form("DEMO-KA-104"),
    batch_id: str = Form("ELEC-DEMO-01"),
    camera_id: str = Form("LAB-CAM-01"),
):
    suffix = Path(file.filename or "video.avi").suffix or ".avi"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)
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
    zones_json: str = Form(...),
    authorization: str = Form("unknown"),
    zone_profile: str = Form(""),
    centre_id: str = Form("DEMO-KA-104"),
    batch_id: str = Form("ELEC-DEMO-01"),
    camera_id: str = Form("LAB-CAM-03"),
):
    """Analyse stable anonymous worker presence + worker-centric motion in work cells.

    Authorization is supplied externally. Vision does not infer identity,
    authorization, skill quality, or exact task semantics.
    """
    try:
        parsed = json.loads(zones_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid work-zone JSON") from exc

    if isinstance(parsed, dict) and isinstance(parsed.get("zones"), list):
        zones = parsed["zones"]
    elif (
        isinstance(parsed, dict)
        and zone_profile
        and isinstance(parsed.get(zone_profile), list)
    ):
        zones = parsed[zone_profile]
    elif isinstance(parsed, list):
        zones = parsed
    else:
        raise HTTPException(
            status_code=400,
            detail=(
                "Work-zone JSON must be a list, contain a 'zones' list, or contain "
                "a list matching the supplied zone profile"
            ),
        )

    suffix = Path(file.filename or "video.mp4").suffix or ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        result = PRACTICAL_PIPELINE.run(
            video_path=tmp_path,
            zones=zones,
            authorization=authorization,
            centre_id=centre_id,
            batch_id=batch_id,
            camera_id=camera_id,
        )
        if result.case:
            STORE.save(result.case)
        return result.model_dump(mode="json")
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
    case = STORE.update_status(case_id, request.action, note=request.note)
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

    roi_values = (roi_x1, roi_y1, roi_x2, roi_y2)
    if any(v is not None for v in roi_values) and not all(v is not None for v in roi_values):
        raise HTTPException(status_code=400, detail="Provide all ROI coordinates or none")
    roi = tuple(int(v) for v in roi_values) if all(v is not None for v in roi_values) else None

    suffix = Path(file.filename or "video.avi").suffix or ".avi"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

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
                "banner": "Prototype — cached equipment detections; no persistent visual manifest exception",
            }
        STORE.save(case)
        return {
            "created": True,
            "banner": (
                "Prototype — uploaded video evidence with cached equipment detections; "
                "not official live compliance data"
            ),
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
    suffix = Path(file.filename or "video.avi").suffix or ".avi"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)
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
