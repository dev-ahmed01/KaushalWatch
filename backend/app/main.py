from __future__ import annotations
import asyncio
from pathlib import Path
from datetime import datetime, timedelta, timezone
import os
import json
import logging
import tempfile
import cv2
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Body, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response, JSONResponse
from app.models import (
    AssistantChatRequest,
    AssistantChatResponse,
    AssistantSpeechRequest,
    AssistantTranscriptionResponse,
    ReviewRequest,
    EdgeSyncRequest,
    ComplianceCase,
)
from app.services.case_store import CaseStore
from app.services.infrastructure import aggregate_cached_observations, compare_manifest
from app.services.infrastructure_pipeline import InfrastructureCompliancePipeline
from app.services.compliance_cases import build_infrastructure_case
from app.services.operability import apparent_motion_state
from app.services.video_pipeline import VideoCompliancePipeline
from app.services.practical_activity_pipeline import PracticalActivityPipeline
from app.services.offline_queue import json_payload_bytes
from app.services.edge_ingest import normalize_event
from app.services.edge_access import resolve_edge_actor, edge_centre_scope
from app.services.edge_event_ledger import EdgeEventLedger
from app.services.demo_assets import (
    load_demo_manifest_and_cache,
    load_demo_equipment_metadata,
    require_equipment_profile_source,
    build_compliant_demo_cache,
)
from app.services.demo_network import DEMO_CENTRES, provisioned_centres, centre_rows, get_centre
from app.services.analysis_history import AnalysisHistoryStore
from app.services.compliance_assistant import answer_question
from app.services.centre_settings import CentreSettingsStore
from app.services.report_pdf import build_report_pdf
from app.services.runtime_readiness import build_runtime_readiness
from app.services.assistant_service import AssistantService, AssistantUnavailableError
from app.services.assistant_tools import AssistantDataContext, KaushalToolset
from app.services.conversation_store import InMemoryConversationStore
from app.services.kaushalai_briefing import build_network_brief
from app.services.centre_intelligence import build_centre_intelligence
from app.services.activity_intelligence import build_activity_intelligence, activity_bucket_for_practical_run
from app.services.evidence_review import build_evidence_review_pack
from app.services.network_insights import build_network_insights
from app.services.action_queue import build_action_queue
from app.services.centre_desk import centre_day, change_task, fixture_tasks, task_history
from app.services.local_chat import list_threads as demo_chat_threads, list_messages as demo_chat_messages, send_text as demo_chat_send, member_by_id as demo_chat_actor, send_voice as demo_chat_voice, read_voice as demo_chat_read_voice, MAX_VOICE_BYTES
from app.services.review_access import LOCAL_ENVS
from app.services.review_access import review_access_status, resolve_review_actor
from app.services.protected_access import protected_read_boundary
from app.services.officer_permissions import require_centre, visible, request_principal
from app.services.api_redaction import redact_local_evidence_paths
from app.services.officer_permissions import evidence_centre
from app.services.object_evidence import fetch_private_evidence, EVIDENCE_ID
from app.services.vision_profile import build_vision_governance, load_vision_profile
from app.services.postgres_store import (
    PostgresCaseStore, PostgresAnalysisHistoryStore, PostgresCentreSettingsStore,
    PostgresEdgeEventLedger, unit_of_work,
)

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
EVIDENCE = DATA / "evidence"
EVIDENCE_BACKEND = os.getenv("KAUSHALWATCH_EVIDENCE_BACKEND", "local").strip().lower()
if EVIDENCE_BACKEND not in {"local", "s3"}:
    raise RuntimeError("Invalid evidence storage backend")
if EVIDENCE_BACKEND == "s3" and os.getenv("KAUSHALWATCH_STORAGE_BACKEND", "json") != "postgres":
    raise RuntimeError("Private S3 evidence storage requires PostgreSQL")
STORAGE_BACKEND = os.getenv("KAUSHALWATCH_STORAGE_BACKEND", "json").strip().lower()
if STORAGE_BACKEND not in {"json", "postgres"}:
    raise RuntimeError("Invalid KaushalWatch storage backend")
if STORAGE_BACKEND == "postgres":
    if not os.getenv("KAUSHALWATCH_DATABASE_URL", "").startswith(("postgres://", "postgresql://")):
        raise RuntimeError("Postgres backend requires KAUSHALWATCH_DATABASE_URL")
    STORE = PostgresCaseStore()
else:
    STORE = CaseStore(DATA / "cases.json")
PIPELINE = VideoCompliancePipeline(EVIDENCE, DATA / "evidence_index.json")
PRACTICAL_PIPELINE = PracticalActivityPipeline(EVIDENCE, DATA / "evidence_index.json", detector=PIPELINE.detector)
DEFAULT_WORK_ZONES = ROOT / "backend" / "app" / "demo_configs" / "work_zones.json"
INFRA_PIPELINE = InfrastructureCompliancePipeline(EVIDENCE, DATA / "evidence_index.json", privacy_detector=PIPELINE.detector)
HISTORY = (PostgresAnalysisHistoryStore() if STORAGE_BACKEND == "postgres"
           else AnalysisHistoryStore(DATA / "analysis_history.json"))
CENTRE_SETTINGS = (PostgresCentreSettingsStore() if STORAGE_BACKEND == "postgres"
                   else CentreSettingsStore(DATA / "centre_settings.json"))
ASSISTANT_SERVICE: AssistantService | None = None
VOICE_SERVICE = None
CONVERSATIONS = InMemoryConversationStore()
VISION_PROFILE = load_vision_profile()
VISION_PROFILE_ID = str(VISION_PROFILE["profile_id"])

ASSISTANT_UNAVAILABLE_MESSAGE = (
    "Kaushal Assistant is temporarily unavailable. "
    "Monitoring and analysis continue to work normally."
)
ASSISTANT_CONFIG_MESSAGE = (
    "Kaushal Assistant requires AI configuration. "
    "Monitoring and analysis continue to work normally."
)
VOICE_CONFIG_MESSAGE = (
    "Kaushal Assistant voice requires Groq configuration. "
    "Typed chat and monitoring continue to work normally."
)
MAX_ASSISTANT_AUDIO_BYTES = 25 * 1024 * 1024
MAX_ASSISTANT_SPEECH_CHARS = 4000
ASSISTANT_AUDIO_TYPES = {
    ".webm": {"audio/webm", "video/webm"},
    ".wav": {"audio/wav", "audio/x-wav"},
    ".mp3": {"audio/mpeg", "audio/mp3"},
    ".mp4": {"audio/mp4", "video/mp4"},
    ".mpeg": {"audio/mpeg", "video/mpeg"},
    ".mpga": {"audio/mpeg"},
    ".m4a": {"audio/mp4", "audio/x-m4a"},
}


def _network_settings() -> dict[str, dict]:
    return {
        centre["centre_id"]: CENTRE_SETTINGS.get(centre["centre_id"])
        for centre in provisioned_centres()
    }


def _network_history() -> dict[str, list[dict]]:
    rows = HISTORY.list(limit=500)
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(str(row.get("centre_id") or ""), []).append(row)
    return grouped


def _centre_with_settings(centre_id: str):
    return get_centre(
        centre_id,
        STORE.list(),
        settings=CENTRE_SETTINGS.get(centre_id),
        history=HISTORY.list(centre_id=centre_id, limit=200),
    )


def _ai_enabled() -> bool:
    return os.getenv("KAUSHAL_AI_ENABLED", "true").strip().lower() not in {
        "0", "false", "no", "off"
    }


def _ai_configured() -> bool:
    return bool((os.getenv("GEMINI_API_KEY") or "").strip())


def _voice_configured() -> bool:
    return bool((os.getenv("GROQ_API_KEY") or "").strip())


def _assistant_timeout_seconds() -> float:
    try:
        value = float(os.getenv("KAUSHAL_AI_TIMEOUT_SECONDS", "60"))
    except ValueError:
        return 60.0
    return min(max(value, 0.001), 300.0)


def get_assistant_service() -> AssistantService:
    global ASSISTANT_SERVICE
    if ASSISTANT_SERVICE is not None:
        return ASSISTANT_SERVICE
    if not _ai_enabled() or not _ai_configured():
        raise RuntimeError(ASSISTANT_CONFIG_MESSAGE)

    from app.services.openai_assistant import OpenAIAssistantProvider

    context = AssistantDataContext(
        history=HISTORY,
        cases=STORE,
        centre_lookup=_centre_with_settings,
        readiness_provider=runtime_readiness,
        network_brief_provider=lambda period: build_network_brief(
            centres=centre_rows(
                STORE.list(),
                settings_by_centre=_network_settings(),
                history_by_centre=_network_history(),
            ),
            cases=STORE.list(),
            history=HISTORY.list(limit=500),
            period=period,
        ),
        activity_intelligence_provider=lambda centre_id, period: build_activity_intelligence(
            centre=_centre_with_settings(centre_id) or {},
            history=HISTORY.list(centre_id=centre_id, limit=500),
            period=period,
        ),
        action_queue_provider=lambda period: build_action_queue(
            centres=centre_rows(
                STORE.list(),
                settings_by_centre=_network_settings(),
                history_by_centre=_network_history(),
            ),
            cases=STORE.list(),
            history=HISTORY.list(limit=500),
            period=period,
        ),
    )
    ASSISTANT_SERVICE = AssistantService(
        provider=OpenAIAssistantProvider(toolset=KaushalToolset(context)),
        conversations=CONVERSATIONS,
    )
    return ASSISTANT_SERVICE


def get_voice_service():
    global VOICE_SERVICE
    if VOICE_SERVICE is not None:
        return VOICE_SERVICE
    if not _ai_enabled() or not _voice_configured():
        raise RuntimeError(VOICE_CONFIG_MESSAGE)
    from app.services.voice_service import VoiceService

    VOICE_SERVICE = VoiceService(timeout_seconds=_assistant_timeout_seconds())
    return VOICE_SERVICE

app = FastAPI(title="KaushalWatch API", version="0.2.0")
_cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "KAUSHALWATCH_CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# No sensitive API/evidence reads are public on a protected network. This
# outermost gate is intentionally separate from edge-device ingestion auth.
# Development SIH walk-throughs are unaffected.
app.middleware("http")(protected_read_boundary)
if EVIDENCE_BACKEND == "local":
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    app.mount("/evidence", StaticFiles(directory=str(EVIDENCE)), name="evidence")
else:
    @app.get("/evidence/{evidence_id}.jpg")
    def get_private_evidence(evidence_id: str, request: Request):
        # Re-check persisted case membership at each read. Never trust an
        # S3 key or caller-provided centre to decide image authorization.
        if not EVIDENCE_ID.fullmatch(evidence_id):
            raise HTTPException(status_code=404, detail="Evidence not found")
        centre = evidence_centre(evidence_id)
        if not centre:
            raise HTTPException(status_code=404, detail="Evidence not found")
        require_centre(request, centre)
        records = [
            record for case in STORE.list() if case.centre_id == centre
            for record in case.evidence if record.evidence_id == evidence_id
        ]
        if len(records) != 1:
            raise HTTPException(status_code=404, detail="Evidence not found")
        try:
            content = fetch_private_evidence(records[0], centre)
        except Exception as exc:
            # Fail closed for integrity, object-store and DB errors. Never
            # leak internal bucket names, paths or credentials to browsers.
            logger.error("Evidence read unavailable: %s", type(exc).__name__)
            raise HTTPException(status_code=503, detail="Evidence is temporarily unavailable") from None
        if content is None:
            raise HTTPException(status_code=404, detail="Evidence not found")
        return Response(
            content, media_type="image/jpeg",
            headers={
                "Cache-Control": "private, no-store, max-age=0",
                "X-Content-Type-Options": "nosniff",
                "Content-Security-Policy": "default-src 'none'; sandbox",
                "Content-Disposition": 'inline; filename="evidence.jpg"',
            },
        )

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


@app.get("/api/ready")
def readiness():
    from app.services.dependency_readiness import dependencies_ready
    if not dependencies_ready():
        return JSONResponse(
            {"ready": False}, status_code=503,
            headers={"Cache-Control": "no-store"},
        )
    return JSONResponse({"ready": True}, headers={"Cache-Control": "no-store"})


@app.get("/api/runtime-readiness")
def runtime_readiness():
    detector = PIPELINE.detector.info
    practical_detector = PRACTICAL_PIPELINE.detector.info
    payload = build_runtime_readiness(
        attendance_detector=detector,
        practical_detector=practical_detector,
        zones_path=DEFAULT_WORK_ZONES,
        evidence_path=EVIDENCE,
    )
    try:
        governance = build_vision_governance(detector=PIPELINE.detector)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        governance = {
            "profile": {
                "profile_id": VISION_PROFILE_ID,
                "valid": False,
                "error": str(exc),
            },
            "runtime_alignment": {
                "aligned": False,
                "note": "Vision profile governance could not be validated.",
            },
        }
    payload["vision_profile"] = governance["profile"]
    payload["runtime_alignment"] = governance["runtime_alignment"]
    return payload


@app.get("/api/vision/governance")
def vision_governance():
    try:
        return build_vision_governance(detector=PIPELINE.detector)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/practical-work-zones")
def practical_work_zones(profile: str = "authorized"):
    if not DEFAULT_WORK_ZONES.exists():
        raise HTTPException(
            status_code=500,
            detail="Bundled practical-work zone configuration is missing",
        )
    try:
        parsed = json.loads(DEFAULT_WORK_ZONES.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=500,
            detail="Bundled practical-work zone configuration is invalid",
        ) from exc

    zones = parsed.get(profile) if isinstance(parsed, dict) else None
    if not isinstance(zones, list):
        raise HTTPException(
            status_code=404,
            detail=f"Unknown practical-work zone profile: {profile}",
        )
    reference = parsed.get("_reference") if isinstance(parsed, dict) else None
    return {
        "profile": profile,
        "reference": reference or {"width": 1920, "height": 1080},
        "zones": zones,
        "note": (
            "Zones are fixed-camera geometry for the bundled demo scene. "
            "They are visualized in the UI and scaled only for the same camera view."
        ),
    }


@app.get("/api/centres")
def list_centres(request: Request):
    rows = centre_rows(
        STORE.list(),
        settings_by_centre=_network_settings(),
        history_by_centre=_network_history(),
    )
    rows = visible(request, rows)
    return {
        "centres": rows,
        "total": len(rows),
    }


@app.get("/api/actions")
def action_queue(request: Request, period: str = "yesterday"):
    centres = centre_rows(
        STORE.list(),
        settings_by_centre=_network_settings(),
        history_by_centre=_network_history(),
    )
    try:
        return build_action_queue(
            centres=visible(request, centres),
            cases=visible(request, STORE.list()),
            history=visible(request, HISTORY.list(limit=500)),
            period=period,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/insights")
def network_insights(request: Request, period: str = "last_7_days"):
    centres = centre_rows(
        STORE.list(),
        settings_by_centre=_network_settings(),
        history_by_centre=_network_history(),
    )
    try:
        return build_network_insights(
            centres=visible(request, centres),
            cases=visible(request, STORE.list()),
            history=visible(request, HISTORY.list(limit=500)),
            period=period,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/kaushalai/brief")
def kaushalai_brief(request: Request, period: str = "yesterday"):
    centres = centre_rows(
        STORE.list(),
        settings_by_centre=_network_settings(),
        history_by_centre=_network_history(),
    )
    try:
        return build_network_brief(
            centres=visible(request, centres),
            cases=visible(request, STORE.list()),
            history=visible(request, HISTORY.list(limit=500)),
            period=period,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/centres/{centre_id}/activity-intelligence")
def centre_activity_intelligence(centre_id: str, period: str = "yesterday"):
    centre = _centre_with_settings(centre_id)
    if not centre:
        raise HTTPException(status_code=404, detail="Centre not found")
    try:
        return build_activity_intelligence(
            centre=centre,
            history=HISTORY.list(centre_id=centre_id, limit=500),
            period=period,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/centres/{centre_id}/intelligence")
def centre_intelligence(centre_id: str, period: str = "last_7_days"):
    centre = _centre_with_settings(centre_id)
    if not centre:
        raise HTTPException(status_code=404, detail="Centre not found")
    try:
        return build_centre_intelligence(
            centre=centre,
            cases=STORE.list(),
            history=HISTORY.list(centre_id=centre_id, limit=500),
            settings=CENTRE_SETTINGS.get(centre_id),
            period=period,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/centres/{centre_id}")
def centre_detail(centre_id: str):
    centre = _centre_with_settings(centre_id)
    if not centre:
        raise HTTPException(status_code=404, detail="Centre not found")
    settings = CENTRE_SETTINGS.get(centre_id)
    history = HISTORY.list(centre_id=centre_id, limit=20)
    return {
        **centre,
        "settings": settings,
        "recent_analyses": history[:6],
    }


@app.get("/api/analysis-history")
def analysis_history(
    request: Request,
    centre_id: str | None = None,
    batch_id: str | None = None,
    limit: int = 100,
):
    if centre_id:
        require_centre(request, centre_id)
    # Scope first: other centres cannot consume the response limit.
    all_rows = HISTORY.list(centre_id=centre_id, batch_id=batch_id, limit=500)
    return {"rows": visible(request, all_rows)[:min(max(limit, 1), 500)]}


@app.get("/api/centres/{centre_id}/settings")
def centre_settings(centre_id: str):
    if not _centre_with_settings(centre_id):
        raise HTTPException(status_code=404, detail="Centre not found")
    return CENTRE_SETTINGS.get(centre_id)


@app.put("/api/centres/{centre_id}/settings")
def update_centre_settings(centre_id: str, payload: dict = Body(...)):
    if not _centre_with_settings(centre_id):
        raise HTTPException(status_code=404, detail="Centre not found")
    return CENTRE_SETTINGS.save(centre_id, payload)


@app.post("/api/assistant/query")
def assistant_query(http_request: Request, payload: dict = Body(...)):
    centre_id = str(payload.get("centre_id") or "DEMO-KA-104")
    require_centre(http_request, centre_id)
    period = str(payload.get("period") or "7d")
    question = str(payload.get("question") or "").strip()
    centre = _centre_with_settings(centre_id)
    if not centre:
        raise HTTPException(status_code=404, detail="Centre not found")
    centre_cases = [case for case in STORE.list() if case.centre_id == centre_id]
    history = HISTORY.list(centre_id=centre_id, limit=200)
    return answer_question(
        question=question,
        centre=centre,
        cases=centre_cases,
        history=history,
        period=period,
    )


@app.get("/api/assistant/status")
def assistant_status():
    enabled = _ai_enabled()
    configured = _ai_configured()
    voice_configured = _voice_configured()
    return {
        "enabled": enabled,
        "configured": configured,
        "available": enabled and configured,
        "voice_configured": voice_configured,
        "voice_available": enabled and voice_configured,
    }


@app.post("/api/assistant/chat", response_model=AssistantChatResponse)
async def assistant_chat(request: AssistantChatRequest):
    if not _centre_with_settings(request.centre_id):
        raise HTTPException(status_code=404, detail="Centre not found")
    try:
        service = get_assistant_service()
        return await asyncio.wait_for(
            service.chat(
                message=request.message,
                session_id=request.session_id,
                centre_id=request.centre_id,
            ),
            timeout=_assistant_timeout_seconds(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except AssistantUnavailableError as exc:
        raise HTTPException(status_code=503, detail=ASSISTANT_UNAVAILABLE_MESSAGE) from exc
    except RuntimeError as exc:
        if str(exc) == ASSISTANT_CONFIG_MESSAGE:
            raise HTTPException(status_code=503, detail=ASSISTANT_CONFIG_MESSAGE) from exc
        raise HTTPException(status_code=503, detail=ASSISTANT_UNAVAILABLE_MESSAGE) from exc
    except TimeoutError as exc:
        logger.warning("assistant chat timed out")
        raise HTTPException(status_code=503, detail=ASSISTANT_UNAVAILABLE_MESSAGE) from exc


@app.post("/api/assistant/transcribe", response_model=AssistantTranscriptionResponse)
async def assistant_transcribe(audio: UploadFile = File(...)):
    filename = audio.filename or "recording.webm"
    suffix = Path(filename).suffix.lower()
    content_type = (audio.content_type or "").split(";", 1)[0].strip().lower()
    if suffix not in ASSISTANT_AUDIO_TYPES or content_type not in ASSISTANT_AUDIO_TYPES[suffix]:
        raise HTTPException(status_code=415, detail="Unsupported or mismatched audio format")

    chunks = []
    total = 0
    while True:
        chunk = await audio.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_ASSISTANT_AUDIO_BYTES:
            raise HTTPException(status_code=413, detail="Audio exceeds the 25 MB upload limit")
        chunks.append(chunk)
    if total == 0:
        raise HTTPException(status_code=400, detail="Uploaded audio is empty")

    try:
        service = get_voice_service()
        text = await asyncio.wait_for(
            service.transcribe(
                filename=filename,
                content_type=content_type,
                data=b"".join(chunks),
            ),
            timeout=_assistant_timeout_seconds(),
        )
        return AssistantTranscriptionResponse(text=text)
    except RuntimeError as exc:
        if str(exc) == VOICE_CONFIG_MESSAGE:
            raise HTTPException(status_code=503, detail=VOICE_CONFIG_MESSAGE) from exc
        raise HTTPException(
            status_code=503, detail="Speech transcription is temporarily unavailable."
        ) from exc
    except Exception as exc:
        logger.exception("assistant transcription failed")
        raise HTTPException(
            status_code=503, detail="Speech transcription is temporarily unavailable."
        ) from exc


@app.post("/api/assistant/speech")
async def assistant_speech(request: AssistantSpeechRequest):
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="text must not be empty")
    if len(text) > MAX_ASSISTANT_SPEECH_CHARS:
        raise HTTPException(
            status_code=422,
            detail=f"text must be at most {MAX_ASSISTANT_SPEECH_CHARS} characters",
        )
    try:
        service = get_voice_service()
        content = await asyncio.wait_for(
            service.speech(text),
            timeout=_assistant_timeout_seconds(),
        )
        return Response(
            content=content,
            media_type="audio/wav",
            headers={"Cache-Control": "no-store"},
        )
    except RuntimeError as exc:
        if str(exc) == VOICE_CONFIG_MESSAGE:
            raise HTTPException(status_code=503, detail=VOICE_CONFIG_MESSAGE) from exc
        raise HTTPException(
            status_code=503, detail="Speech generation is temporarily unavailable."
        ) from exc
    except Exception as exc:
        logger.exception("assistant speech generation failed")
        raise HTTPException(
            status_code=503, detail="Speech generation is temporarily unavailable."
        ) from exc


def _report_window(
    period: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> tuple[datetime, datetime, str]:
    now = datetime.now(timezone.utc)
    today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)

    if period == "custom":
        if not start_date or not end_date:
            raise HTTPException(
                status_code=422,
                detail="Custom report range requires start_date and end_date",
            )
        try:
            start = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
            end_day = datetime.fromisoformat(end_date).replace(tzinfo=timezone.utc)
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail="Custom dates must use YYYY-MM-DD",
            ) from exc
        end = end_day + timedelta(days=1)
        if end <= start:
            raise HTTPException(status_code=422, detail="end_date must be on or after start_date")
        return start, end, f"{start_date} to {end_date}"

    if period == "today":
        return today_start, now, "Today"
    if period == "yesterday":
        return today_start - timedelta(days=1), today_start, "Yesterday"
    if period == "30d":
        return now - timedelta(days=30), now, "Last 30 days"
    return now - timedelta(days=7), now, "Last 7 days"


def _build_centre_report(
    centre_id: str,
    period: str = "7d",
    start_date: str | None = None,
    end_date: str | None = None,
):
    centre = _centre_with_settings(centre_id)
    if not centre:
        raise HTTPException(status_code=404, detail="Centre not found")
    history = HISTORY.list(centre_id=centre_id, limit=500)
    start, end, period_label = _report_window(period, start_date, end_date)

    def _recent(row):
        try:
            created = datetime.fromisoformat(str(row.get("created_at", "")).replace("Z", "+00:00"))
        except ValueError:
            return True
        return start <= created < end

    history = [row for row in history if _recent(row)]
    cases = [case for case in STORE.list() if case.centre_id == centre_id]
    pending = [
        case for case in cases
        if case.status.value in {"open", "under_review", "virtual_verification"}
    ]
    simulated = any(
        bool((row.get("details") or {}).get("simulated"))
        for row in history
    ) or any(bool(case.details.get("simulated")) for case in cases)

    return {
        "title": "KaushalWatch Centre Verification Report",
        "prototype": True,
        "simulated": simulated,
        "period": period,
        "period_label": period_label,
        "start_date": start_date,
        "end_date": end_date,
        "centre": centre,
        "summary": {
            "analysis_runs": len(history),
            "pending_cases": len(pending),
            "escalation": centre["escalation"],
        },
        "analyses": history,
        "cases": [redact_local_evidence_paths(case.model_dump(mode="json")) for case in cases],
        "privacy_note": (
            "No facial recognition is used for attendance verification. "
            "Visual outputs are aggregate or anonymous and final action requires human review."
        ),
        "limitations": [
            "Infrastructure demo counts are stage-safe telemetry until a live equipment detector is connected.",
            "Apparent operability is a visual activity proxy, not a mechanical or electrical diagnosis.",
            "A pending or blocked verification is never reported as compliant.",
        ],
    }


@app.get("/api/centres/{centre_id}/report")
def centre_report(
    centre_id: str,
    request: Request,
    period: str = "7d",
    start_date: str | None = None,
    end_date: str | None = None,
):
    require_centre(request, centre_id)
    return _build_centre_report(centre_id, period, start_date, end_date)


@app.get("/api/centres/{centre_id}/report.pdf")
def centre_report_pdf(
    centre_id: str,
    request: Request,
    period: str = "7d",
    start_date: str | None = None,
    end_date: str | None = None,
):
    require_centre(request, centre_id)
    report = _build_centre_report(centre_id, period, start_date, end_date)
    content = build_report_pdf(report)
    filename = f"KaushalWatch-{centre_id}-{period}.pdf"
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/dashboard")
def dashboard(
    centre_id: str | None = None,
    batch_id: str | None = None,
    request: Request = None,
):
    if centre_id:
        require_centre(request, centre_id)
    all_cases = visible(request, STORE.list())
    if STORAGE_BACKEND == "postgres":
        edge_events = PostgresEdgeEventLedger().load()
    else:
        edge_events_path = DATA / "edge_events.json"
        edge_events = json.loads(edge_events_path.read_text()) if edge_events_path.exists() else []
    principal = request_principal(request)
    if principal is not None and not principal.is_admin:
        # Unknown event shapes never reveal global edge telemetry to scoped officers.
        edge_events = [
            row for row in edge_events
            if isinstance(row, dict)
            and isinstance(row.get("payload"), dict)
            and row["payload"].get("centre_id") in principal.centres
        ]
    pending_statuses = {"open", "under_review", "virtual_verification"}

    global_pending_cases = [
        case for case in all_cases if case.status.value in pending_statuses
    ]

    cases = all_cases
    if centre_id:
        cases = [case for case in cases if case.centre_id == centre_id]
    if batch_id:
        cases = [case for case in cases if case.batch_id == batch_id]

    pending_cases = [case for case in cases if case.status.value in pending_statuses]
    resolved_cases = [case for case in cases if case.status.value not in pending_statuses]

    return {
        "banner": "Prototype — Simulated Operational Data",
        "centres_monitored": (
            4 if principal is None else
            len(provisioned_centres()) if principal.is_admin else len(principal.centres)
        ),
        "scope": {
            "centre_id": centre_id,
            "batch_id": batch_id,
            "is_filtered": bool(centre_id or batch_id),
        },
        "open_cases": len(pending_cases),
        "global_open_cases": len(global_pending_cases),
        "resolved_cases": len(resolved_cases),
        "camera_issues": sum(
            case.case_type == "camera_integrity"
            and case.status.value in pending_statuses
            for case in cases
        ),
        "synced_edge_events": len(edge_events),
        "edge_sync_state": "idle" if not edge_events else "synced",
        "pending_cases": [redact_local_evidence_paths(case.model_dump(mode="json")) for case in pending_cases[-20:]],
        "resolved_case_history": [redact_local_evidence_paths(case.model_dump(mode="json")) for case in resolved_cases[-20:]],
        "cases": [redact_local_evidence_paths(case.model_dump(mode="json")) for case in cases[-40:]],
    }


@app.post("/api/process-video")
def process_video(
    http_request: Request,
    file: UploadFile = File(...),
    reported_attendance: int = Form(...),
    centre_id: str = Form("DEMO-KA-104"),
    batch_id: str = Form("ELEC-DEMO-01"),
    camera_id: str = Form("LAB-CAM-01"),
):
    require_centre(http_request, centre_id, write=True)
    tmp_path = _materialize_video_upload(file)
    try:
        result = PIPELINE.run(tmp_path, reported_attendance, centre_id, batch_id, camera_id=camera_id)
        if result.case:
            result.case.details["vision_profile_id"] = VISION_PROFILE_ID
            STORE.save(result.case)
        # A detector being installed is not sufficient to assert attendance
        # compliance. The full temporal pipeline must explicitly decide that
        # the video is compliant and contain no detector failures or trust gap.
        attendance_verified = (
            result.decision == "compliant"
            and result.case is None
            and result.detector_authoritative
            and result.detector_failures == 0
            and result.trusted_sample_ratio >= 0.5
        )
        attendance_blocked = (
            result.decision in {"camera_integrity_exception", "camera_evidence_insufficient", "detector_unavailable"}
            or not result.detector_authoritative
            or result.detector_failures > 0
            or result.trusted_sample_ratio < 0.5
        )
        HISTORY.append(
            centre_id=centre_id,
            batch_id=batch_id,
            analysis_type="attendance",
            outcome="compliant" if attendance_verified else (
                "blocked" if attendance_blocked or result.case is None else "attention"
            ),
            summary=(
                "Attendance matched the reported record."
                if attendance_verified
                else "Attendance verification blocked by insufficient camera or detector evidence."
                if attendance_blocked
                else result.case.summary if result.case else
                "Attendance verification remains unresolved and requires review."
            ),
            details={
                "reported_attendance": result.reported_attendance,
                "estimated_occupancy": result.estimated_occupancy,
                "discrepancy_pct": result.discrepancy_pct,
                "decision": result.decision,
                "vision_profile_id": VISION_PROFILE_ID,
            },
        )
        return redact_local_evidence_paths(result.model_dump(mode="json"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        tmp_path.unlink(missing_ok=True)


@app.post("/api/process-practical-activity")
def process_practical_activity(
    http_request: Request,
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
    require_centre(http_request, centre_id, write=True)
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
        analysis_started_at = datetime.now(timezone.utc)
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
            result.case.details["vision_profile_id"] = VISION_PROFILE_ID
            STORE.save(result.case)
        HISTORY.append(
            centre_id=centre_id,
            batch_id=batch_id,
            analysis_type="practical_work",
            outcome="attention" if result.case else (
                "blocked"
                if result.decision in {"camera_evidence_insufficient", "detector_unavailable"}
                or not result.detector_authoritative
                else "compliant"
            ),
            summary=(
                result.case.summary
                if result.case
                else (
                    "Authorized practical activity was observed."
                    if result.decision == "authorized_practical_activity"
                    else result.detector_message
                    if result.decision == "detector_unavailable"
                    else "No practical-work exception was created."
                )
            ),
            details={
                "decision": result.decision,
                "active_work_cells": result.active_work_cells,
                "peak_stable_workers": result.peak_stable_workers,
                "activity_fraction": result.practical_activity_fraction,
                "detector_backend": result.detector_backend,
                "detector_authoritative": result.detector_authoritative,
                "detector_failures": result.detector_failures,
                "vision_profile_id": VISION_PROFILE_ID,
                "activity_buckets": [
                    activity_bucket_for_practical_run(
                        start_at=analysis_started_at,
                        duration_sec=result.duration_sec,
                        activity_score=result.practical_activity_fraction,
                        trusted_frame_ratio=result.trusted_frame_ratio,
                        active_work_cells=result.active_work_cells,
                    )
                ],
            },
        )
        return redact_local_evidence_paths(result.model_dump(mode="json"))
    except RuntimeError as exc:
        message = str(exc)
        HISTORY.append(
            centre_id=centre_id,
            batch_id=batch_id,
            analysis_type="practical_work",
            outcome="blocked",
            summary=message,
            details={
                "decision": "detector_unavailable",
                "active_work_cells": 0,
                "peak_stable_workers": 0,
                "activity_fraction": 0.0,
                "vision_profile_id": VISION_PROFILE_ID,
            },
        )
        return {
            "centre_id": centre_id,
            "batch_id": batch_id,
            "camera_id": camera_id,
            "authorization": authorization,
            "decision": "detector_unavailable",
            "detector_backend": "unavailable",
            "detector_mode": "blocked",
            "detector_authoritative": False,
            "detector_message": message,
            "detector_failures": 1,
            "zone_scaled": False,
            "zone_reference_width": zone_reference_size[0] if zone_reference_size else None,
            "zone_reference_height": zone_reference_size[1] if zone_reference_size else None,
            "frames_processed": 0,
            "duration_sec": 0.0,
            "trusted_frame_ratio": 0.0,
            "peak_stable_workers": 0,
            "practical_activity_fraction": 0.0,
            "first_practical_activity_time_sec": None,
            "active_work_cells": 0,
            "work_cells": [],
            "case": None,
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        tmp_path.unlink(missing_ok=True)


@app.get("/api/cases")
def list_cases(request: Request):
    return [redact_local_evidence_paths(c.model_dump(mode="json"))
            for c in visible(request, STORE.list())]


@app.get("/api/cases/{case_id}/evidence-pack")
def get_evidence_pack(case_id: str, request: Request):
    case = STORE.get(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    # Match list/report/evidence access boundaries: the case ID must not
    # reveal another centre's saved images, decision notes or audit history.
    require_centre(request, case.centre_id)
    return redact_local_evidence_paths(build_evidence_review_pack(
        case=case,
        history=HISTORY.list(centre_id=case.centre_id, limit=500),
    ))


@app.get("/api/review-access")
def get_review_access():
    return review_access_status()

@app.get("/api/officer-validate")
def validate_protected_officer_login(
    officer_actor: str = Depends(resolve_review_actor),
):
    """Validate a server-mapped officer key ONLY in explicitly protected mode.

    A demo/development backend must never authenticate a protected web browser
    by allowing a public read with an arbitrary key.
    """
    from app.services.review_access import PROTECTED_ENVS
    environment = os.getenv("KAUSHALWATCH_ENV", "development").strip().lower()
    if environment not in PROTECTED_ENVS:
        raise HTTPException(status_code=503, detail="Protected officer login requires protected API mode.")
    return {"authenticated": True}


@app.get("/api/officer-context")
def officer_context(request: Request):
    """Expose only non-secret role/centre grants to the protected UI."""
    principal = request_principal(request)
    if principal is None:
        return {"mode": "demo", "role": "demo_officer", "centre_ids": [],
                "can_review": True, "can_use_network_assistant": True}
    return {
        "mode": "protected", "role": principal.role,
        "centre_ids": sorted(principal.centres),
        "can_review": principal.can_write,
        "can_use_network_assistant": principal.is_admin,
    }


@app.post("/api/cases/{case_id}/review")
def review_case(
    case_id: str,
    request: ReviewRequest,
    officer_actor: str = Depends(resolve_review_actor),
):
    terminal_actions = {"confirmed", "false_positive", "resolved"}
    note = (request.note or "").strip()
    if request.action.value in terminal_actions and not note:
        raise HTTPException(
            status_code=422,
            detail="A review note is required for a final case decision",
        )

    try:
        case = STORE.apply_review_action(
            case_id,
            request.action,
            note=note or None,
            actor=officer_actor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return redact_local_evidence_paths(case.model_dump(mode="json"))


@app.get("/api/demo/infrastructure")
def infrastructure_demo(profile: str = "compliant"):
    try:
        manifest, rows = load_demo_manifest_and_cache()
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    equipment_profile = {}
    if profile == "compliant":
        rows = build_compliant_demo_cache(manifest)
    elif profile == "discrepancy":
        equipment_profile = load_demo_equipment_metadata()
    else:
        raise HTTPException(
            status_code=400,
            detail="profile must be 'compliant' or 'discrepancy'",
        )

    observed = aggregate_cached_observations(rows)
    return {
        "banner": (
            "Prototype — explicit compliant demo telemetry"
            if profile == "compliant"
            else "Prototype — human-reviewed GroundingDINO equipment profile"
        ),
        "job_role": manifest["job_role"],
        "profile": profile,
        "equipment_profile": equipment_profile,
        "items": compare_manifest(manifest, observed),
    }




@app.post("/api/process-infrastructure-video")
def process_infrastructure_video(
    http_request: Request,
    file: UploadFile = File(...),
    centre_id: str = Form("DEMO-KA-104"),
    batch_id: str = Form("ELEC-DEMO-01"),
    camera_id: str = Form("LAB-CAM-02"),
    demo_profile: str = Form("compliant"),
    operability_item_id: str | None = Form(None),
    roi_x1: int | None = Form(None),
    roi_y1: int | None = Form(None),
    roi_x2: int | None = Form(None),
    roi_y2: int | None = Form(None),
    operability_start_sec: float | None = Form(None),
    operability_end_sec: float | None = Form(None),
):
    """Stage-safe infrastructure pipeline using the demo manifest + cached detections.

    The uploaded video supplies actual evidence and optional operability frames.
    Equipment observations are currently sourced from the cached detector adapter;
    GroundingDINO can replace that adapter without changing the case workflow.
    """
    require_centre(http_request, centre_id, write=True)
    try:
        manifest, rows = load_demo_manifest_and_cache()
        equipment_profile = load_demo_equipment_metadata()
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

    window_values = (operability_start_sec, operability_end_sec)
    if any(v is not None for v in window_values) and not all(v is not None for v in window_values):
        raise HTTPException(
            status_code=400,
            detail="Provide both operability_start_sec and operability_end_sec or neither",
        )
    operability_window = (
        tuple(float(v) for v in window_values)
        if all(v is not None for v in window_values)
        else None
    )
    if demo_profile == "discrepancy":
        profile_operability = equipment_profile.get("operability") or {}
        profile_roi = profile_operability.get("roi") or {}
        profile_window = profile_operability.get("window") or {}
        if roi is None and all(k in profile_roi for k in ("x1", "y1", "x2", "y2")):
            roi = tuple(int(profile_roi[k]) for k in ("x1", "y1", "x2", "y2"))
        if operability_window is None and all(
            k in profile_window for k in ("start_sec", "end_sec")
        ):
            operability_window = (
                float(profile_window["start_sec"]),
                float(profile_window["end_sec"]),
            )
        if not operability_item_id:
            operability_item_id = profile_operability.get("item_id")

    if operability_window is not None and roi is None:
        raise HTTPException(
            status_code=400,
            detail="Operability window requires all ROI coordinates",
        )
    if roi is not None and not operability_item_id:
        operability_item_id = "drill_machine"

    tmp_path = _materialize_video_upload(file)

    try:
        source_match = None
        if demo_profile == "discrepancy":
            source_match = require_equipment_profile_source(
                tmp_path,
                equipment_profile,
            )
        case = INFRA_PIPELINE.run(
            video_path=tmp_path,
            manifest=manifest,
            detection_rows=rows,
            centre_id=centre_id,
            batch_id=batch_id,
            camera_id=camera_id,
            operability_item_id=operability_item_id if roi else None,
            operability_roi=roi,
            operability_window=operability_window,
        )
        if not case:
            HISTORY.append(
                centre_id=centre_id,
                batch_id=batch_id,
                analysis_type="infrastructure",
                outcome="compliant",
                summary="Infrastructure demo profile completed without a persistent visual exception.",
                details={
                    "demo_profile": demo_profile,
                    "items": preview_items,
                    "vision_profile_id": VISION_PROFILE_ID,
                },
            )
            return {
                "created": False,
                "banner": (
                    "Prototype — explicit compliant demo profile; no persistent "
                    "visual manifest exception"
                    if demo_profile == "compliant"
                    else "Prototype — cached equipment detections; no persistent visual manifest exception"
                ),
                "demo_profile": demo_profile,
                "equipment_profile": equipment_profile if demo_profile == "discrepancy" else {},
                "profile_source_match": source_match,
                "items": preview_items,
            }
        case.details["vision_profile_id"] = VISION_PROFILE_ID
        STORE.save(case)
        HISTORY.append(
            centre_id=centre_id,
            batch_id=batch_id,
            analysis_type="infrastructure",
            outcome="attention",
            summary=case.summary,
            details={
                "demo_profile": demo_profile,
                "items": preview_items,
                "vision_profile_id": VISION_PROFILE_ID,
            },
        )
        return {
            "created": True,
            "banner": (
                "Prototype — uploaded video evidence with cached equipment detections; "
                "not official live compliance data"
            ),
            "demo_profile": demo_profile,
            "equipment_profile": equipment_profile if demo_profile == "discrepancy" else {},
            "profile_source_match": source_match,
            "items": preview_items,
            "case": redact_local_evidence_paths(case.model_dump(mode="json")),
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
            "vision_profile_id": VISION_PROFILE_ID,
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
        "case": redact_local_evidence_paths(case.model_dump(mode="json")),
    }



@app.post("/api/edge/sync")
def edge_sync(request: EdgeSyncRequest, edge_actor: str = Depends(resolve_edge_actor)):
    """Ingest sanitized, explicitly unverified edge telemetry atomically per worker."""
    with EdgeEventLedger._lock:
        return _edge_sync_locked(request, edge_actor)


def _edge_sync_locked(request: EdgeSyncRequest, edge_actor: str):
    if STORAGE_BACKEND == "postgres":
        # Receipt acknowledgment, case insert and history insert commit as one
        # transaction, serialized across backend processes by an advisory lock.
        with unit_of_work(edge=True):
            return _edge_sync_execute(request, edge_actor)
    return _edge_sync_execute(request, edge_actor)


def _edge_sync_execute(request: EdgeSyncRequest, edge_actor: str):
    ledger = (PostgresEdgeEventLedger() if STORAGE_BACKEND == "postgres"
              else EdgeEventLedger(DATA / "edge_events.json"))
    rows = ledger.load()
    accepted: list[str] = []
    rejected: list[dict[str, str]] = []
    skipped_existing_case_ids: list[str] = []
    existing = {row.get("event_id"): row for row in rows}
    already_accepted: list[str] = []
    authorised_centres = edge_centre_scope(edge_actor)

    for incoming in request.events:
        event, rejection = normalize_event(incoming)
        if rejection:
            rejected.append({
                "event_id": str(incoming.get("event_id") or "")[:96] if isinstance(incoming, dict) else "",
                "reason": rejection,
            })
            continue
        event_id = event["event_id"]
        if authorised_centres is not None and event["payload"]["centre_id"] not in authorised_centres:
            rejected.append({"event_id": event_id, "reason": "device_centre_scope_denied"})
            continue
        if event_id in existing:
            # A lost HTTP acknowledgement must not strand the durable queue.
            # Re-ACK only an *identical* previously accepted event belonging
            # to the same authenticated edge device and centre.
            previous = dict(existing[event_id])
            actor = previous.pop("server_resolved_edge_actor", None)
            if actor == edge_actor and previous == event:
                already_accepted.append(event_id)
            else:
                rejected.append({"event_id": event_id, "reason": "event_id_conflict"})
            continue
        event["server_resolved_edge_actor"] = edge_actor

        event_type = event["event_type"]
        payload = event["payload"]

        if event_type == "analysis_summary":
            centre_id = str(payload.get("centre_id") or "")
            batch_id = str(payload.get("batch_id") or "")
            analysis_type = str(payload.get("analysis_type") or "")
            outcome = str(payload.get("outcome") or "")
            if centre_id and batch_id and analysis_type and outcome:
                HISTORY.append_edge_once(
                    edge_event_id=event_id,
                    centre_id=centre_id,
                    batch_id=batch_id,
                    analysis_type=analysis_type,
                    outcome=outcome,
                    summary=str(payload.get("summary") or "Edge analysis completed."),
                    details={
                        **(payload.get("details") or {}),
                        "edge_synced": True,
                        "raw_video_uploaded": False,
                        "edge_receipt_unverified": True,
                        "edge_actor": edge_actor,
                        "edge_event_id": event_id,
                    },
                )

        elif event_type == "compliance_case":
            required = {
                "case_id",
                "centre_id",
                "batch_id",
                "case_type",
                "severity",
                "summary",
            }
            if required.issubset(payload):
                incoming_case_id = str(payload["case_id"])
                # Each edge event may have its own event_id. Do not replace a
                # persisted case (especially its officer review/audit history)
                # just because the same case_id appears in a later sync.
                if STORE.get(incoming_case_id) is not None:
                    skipped_existing_case_ids.append(incoming_case_id)
                    rows.append(event)
                    existing[event_id] = event
                    accepted.append(event_id)
                    continue

                case = ComplianceCase(
                    case_id=incoming_case_id,
                    centre_id=str(payload["centre_id"]),
                    batch_id=str(payload["batch_id"]),
                    case_type=str(payload["case_type"]),
                    # Edge inference is never an officer decision. Imported
                    # cases must start open regardless of any source status.
                    status="open",
                    severity=str(payload["severity"]),
                    summary=str(payload["summary"]),
                    reported_attendance=payload.get("reported_attendance"),
                    visual_occupancy=payload.get("visual_occupancy"),
                    discrepancy_pct=payload.get("discrepancy_pct"),
                    persistence_ratio=payload.get("persistence_ratio"),
                    evidence=[],
                    details={
                        **(payload.get("details") or {}),
                        "edge_synced": True,
                        "raw_video_uploaded": False,
                        "edge_receipt_unverified": True,
                        "edge_actor": edge_actor,
                        "edge_event_id": event_id,
                        "edge_reported_status_unverified": str(payload.get("status") or "open"),
                        "edge_evidence_integrity": payload.get("evidence_integrity") or [],
                    },
                    created_at=str(payload.get("created_at") or event.get("created_at") or datetime.now(timezone.utc).isoformat()),
                )
                # Atomic against officer review in the same process. The
                # earlier existence check is only a fast path, never a
                # substitute for this compare-and-insert critical section.
                if not STORE.save_if_absent(case):
                    skipped_existing_case_ids.append(incoming_case_id)

        rows.append(event)
        existing[event_id] = event
        accepted.append(event_id)

    if accepted:
        ledger.save(rows)
    return {
        "accepted_event_ids": accepted + already_accepted,
        "accepted_count": len(accepted),
        "already_accepted_event_ids": already_accepted,
        "duplicate_count": len(already_accepted),
        "rejected_events": rejected,
        "rejected_count": len(rejected),
        "skipped_existing_case_ids": skipped_existing_case_ids,
        "received_payload_bytes": json_payload_bytes(request.events),
        "raw_video_required": False,
    }

# Camera Trust is an isolated shadow workflow; protected_read_boundary is reused.
from app.camera_trust_api import router as camera_trust_router
app.include_router(camera_trust_router)


# Centre Desk fixtures are confined to the synthetic controlled workspace.
# Protected users must not mistake seeded staff schedules for real rosters.
def _require_controlled_centre_desk(request: Request, centre_id: str | None = None) -> dict:
    if os.getenv("KAUSHALWATCH_ENV", "development").strip().lower() not in LOCAL_ENVS:
        raise HTTPException(status_code=503, detail="Centre Desk needs a provisioned staff/schedule integration in protected mode")
    options = visible(request, provisioned_centres())
    requested = centre_id or (options[0]["centre_id"] if options else "")
    centre = next((row for row in options if row["centre_id"] == requested), None)
    if not centre:
        raise HTTPException(status_code=404, detail="Centre not found")
    return centre


@app.get("/api/centre-desk")
def get_centre_desk(request: Request, centre_id: str | None = None):
    centre = _require_controlled_centre_desk(request, centre_id)
    return {"centres": [{"centre_id": item["centre_id"], "name": item["name"]}
                         for item in visible(request, provisioned_centres())],
            "day": centre_day(DATA / "centre_desk_demo.sqlite3", centre)}


@app.post("/api/centre-desk/{centre_id}/tasks/{task_id}/status")
def update_centre_desk_task(centre_id: str, task_id: str, request: Request, payload: dict = Body(...)):
    _require_controlled_centre_desk(request, centre_id)
    if set(payload) != {"status"} or not isinstance(payload.get("status"), str):
        raise HTTPException(status_code=422, detail="Expected task status")
    try:
        task = change_task(DATA / "centre_desk_demo.sqlite3", centre_id, task_id, payload["status"])
    except LookupError:
        raise HTTPException(status_code=404, detail="Task not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"task": task, "audit": task_history(DATA / "centre_desk_demo.sqlite3", centre_id, task_id)}


def _controlled_chat_actor(request: Request) -> str:
    if os.getenv("KAUSHALWATCH_ENV", "development").strip().lower() not in LOCAL_ENVS:
        raise HTTPException(status_code=503, detail="Chatbox needs provisioned staff authentication in protected mode")
    actor=request.headers.get("X-KW-Demo-Actor", "").strip()
    if not actor or not demo_chat_actor(actor):
        raise HTTPException(status_code=403, detail="A recognised synthetic demo role is required")
    return actor

@app.get("/api/chatbox/threads")
def chatbox_threads(request: Request):
    actor=_controlled_chat_actor(request)
    try:
        return demo_chat_threads(DATA / "chatbox_demo.sqlite3",actor)
    except LookupError:
        raise HTTPException(status_code=404, detail="Conversations not found") from None

@app.get("/api/chatbox/threads/{thread_id}/messages")
def chatbox_messages(thread_id: str, request: Request, limit: int = 75):
    actor=_controlled_chat_actor(request)
    try:
        return {"messages": demo_chat_messages(DATA / "chatbox_demo.sqlite3",thread_id,actor,limit)}
    except LookupError:
        raise HTTPException(status_code=404, detail="Conversation not found") from None

@app.post("/api/chatbox/threads/{thread_id}/messages")
def chatbox_send_text(thread_id: str, request: Request, payload: dict = Body(...)):
    actor=_controlled_chat_actor(request)
    if set(payload)!={"body","idempotency_key"} or not all(isinstance(x,str) for x in payload.values()):
        raise HTTPException(status_code=422, detail="Text and idempotency key required")
    try:
        message=demo_chat_send(DATA / "chatbox_demo.sqlite3",thread_id,actor,
                               payload["body"],payload["idempotency_key"])
    except LookupError:
        raise HTTPException(status_code=404, detail="Conversation not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"message":message}


@app.post("/api/chatbox/threads/{thread_id}/voice")
async def chatbox_voice_upload(thread_id: str, request: Request,
    audio: UploadFile = File(...), idempotency_key: str = Form(...),
    duration_ms: int = Form(...)):
    actor=_controlled_chat_actor(request)
    content_type=(audio.content_type or "").split(";",1)[0].lower().strip()
    blob=await audio.read(MAX_VOICE_BYTES + 1)
    try:
        message=demo_chat_voice(DATA / "chatbox_demo.sqlite3",thread_id,actor,blob,
                                content_type,duration_ms,idempotency_key)
    except LookupError:
        raise HTTPException(status_code=404,detail="Conversation not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=422,detail=str(exc)) from exc
    return {"message":message}

@app.get("/api/chatbox/voice/{message_id}")
def chatbox_voice_download(message_id: str, request: Request):
    actor=_controlled_chat_actor(request)
    # Lookup is centre and participant-scoped on every retrieval.
    try:
        media,media_type=demo_chat_read_voice(DATA / "chatbox_demo.sqlite3",
                                               message_id,actor)
    except LookupError:
        raise HTTPException(status_code=404,detail="Voice note not found") from None
    except (OSError,ValueError) as exc:
        logger.warning("Chatbox voice integrity unavailable: %s",type(exc).__name__)
        raise HTTPException(status_code=503,detail="Voice note unavailable") from None
    return Response(content=media,media_type=media_type,headers={
        "Cache-Control":"private, no-store",
        "X-Content-Type-Options":"nosniff",
        "Content-Security-Policy":"default-src 'none'",
    })
