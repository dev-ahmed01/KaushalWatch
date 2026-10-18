"""Read-only local dashboard. No video, camera frames or model credentials served."""
from __future__ import annotations
from pathlib import Path
import json
import hashlib
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

STATIC = Path(__file__).with_name('static')
REPORT_STATUS = 'OFFLINE_DEVELOPMENT_EVIDENCE_ANALYZED_NO_PHYSICAL_TRUTH'


def create_app(report_file: Path, concordance_file: Path | None = None,
               clip_report_file: Path | None = None,
               acceptance_file: Path | None = None,
               external_scenes_file: Path | None = None) -> FastAPI:
    data = json.loads(Path(report_file).read_text(encoding='utf-8'))
    if (data.get('status') != REPORT_STATUS or
            data.get('production_qualified') is not False or
            data.get('false_alarm_rate_known') is not False):
        raise ValueError('Refusing to serve non-research or inconsistent evidence')
    concordance = None
    if concordance_file is not None and Path(concordance_file).is_file():
        from .concordance import VERSION
        concordance = json.loads(Path(concordance_file).read_text(encoding='utf-8'))
        if concordance.get('status') != VERSION or concordance.get('physical_ground_truth_available') is not False:
            raise ValueError('Invalid Phase3W concordance evidence')
        if concordance.get('full_report_sha256') != hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest():
            raise ValueError('Phase3W concordance is stale for the served video evidence')
        if concordance.get('input_phase3r_s_checksum') != data.get('source_evidence_sha256'):
            raise ValueError('Phase3W concordance source differs from served evidence')
    clip_diagnostics = None
    if clip_report_file and Path(clip_report_file).is_file():
        clip_diagnostics = json.loads(Path(clip_report_file).read_text(encoding='utf-8'))
        from .clip_engine import VERSION
        if (clip_diagnostics.get('status') != VERSION or
            clip_diagnostics.get('production_qualified') is not False or
            clip_diagnostics.get('physical_camera_tampering_proven') is not False or
            clip_diagnostics.get('media_or_frames_exported') is not False):
            raise ValueError('Refuse non-research clip results or media export')
    readiness = None
    if acceptance_file is not None and Path(acceptance_file).is_file():
        from .product_readiness import VERSION, sha_json
        readiness=json.loads(Path(acceptance_file).read_text(encoding='utf-8'))
        if (readiness.get('status')!=VERSION or
                readiness.get('production_qualified') is not False or
                readiness.get('source_continuity',{}).get('video_feature_report_sha256') != sha_json(data) or
                (clip_diagnostics is not None and
                 readiness.get('source_continuity',{}).get('source_clip_report_sha256') != sha_json(clip_diagnostics))):
            raise ValueError('Product-readiness receipt differs from served source evidence')
    external_scenes = None
    if external_scenes_file is not None and Path(external_scenes_file).is_file():
        from .product_readiness import audit_external_scenes, sha_json
        external_scenes=json.loads(Path(external_scenes_file).read_text(encoding='utf-8'))
        audit_external_scenes(external_scenes)
        if readiness is not None and readiness.get('source_continuity',{}).get('additional_unlabeled_scenes_sha256') != sha_json(external_scenes):
            raise ValueError('Extra unannotated video evidence differs from product acceptance receipt')
    app = FastAPI(title='KaushalWatch Camera Trust • Research Workstation',
                  docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware('http')
    async def local_security(request: Request, call_next):
        host = request.headers.get('host', '').split(':')[0].lower()
        if host not in ('localhost', '127.0.0.1', 'testserver'):
            return JSONResponse({'error': 'Local workstation only'}, status_code=403)
        if request.method not in ('GET', 'HEAD'):
            return JSONResponse({'error': 'Read-only workstation'}, status_code=405)
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; object-src 'none'; frame-ancestors 'none'; "
            "base-uri 'none'; form-action 'none'"
        )
        response.headers['Referrer-Policy'] = 'no-referrer'
        return response

    @app.get('/api/health')
    def health():
        return {'status': 'research-workstation-ready',
                'production_qualified': False,
                'video_evidence_mounted': data['recordings_available_in_workspace']}

    @app.get('/api/external-scene-probe')
    def external_scene_probe():
        if external_scenes is None:
            raise HTTPException(status_code=404, detail='Additional unannotated scene comparison unavailable')
        return external_scenes

    @app.get('/api/product-readiness')
    def product_readiness():
        if readiness is None:
            raise HTTPException(status_code=404, detail='Independent product acceptance receipt not configured')
        return readiness

    @app.get('/api/report')
    def report():
        return data

    @app.get('/api/concordance')
    def concordance_report():
        if concordance is None:
            raise HTTPException(status_code=404, detail='Full AVI concordance not available')
        return concordance

    @app.get('/api/clip-diagnostics')
    def clip_diagnostics_report():
        if clip_diagnostics is None:
            raise HTTPException(status_code=404, detail='Labeled clip diagnostics unavailable')
        return clip_diagnostics

    @app.get('/api/case/{case_id}')
    def case(case_id: str):
        # Only exact IDs from the already validated numeric report.
        for item in data['priority_queue']:
            if item['id'] == case_id:
                return item
        raise HTTPException(status_code=404, detail='Unknown sampled evidence window')

    @app.get('/', response_class=HTMLResponse)
    def home():
        return (STATIC / 'index.html').read_text(encoding='utf-8')

    app.mount('/static', StaticFiles(directory=STATIC), name='static')
    return app
