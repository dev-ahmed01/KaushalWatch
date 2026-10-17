"""Officer-authenticated, centre-scoped camera reference metadata routes.

Staging-only, explicit feature flag, PostgreSQL required, reference binding
ALWAYS disabled. No request-supplied officer identity/role, no media upload.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from app.services.demo_network import DEMO_CENTRES
from app.services.officer_permissions import OfficerPrincipal
from app.services.protected_camera_reference import (
    ProtectedCameraReferenceWorkflow,
    CameraReferenceConflict,
    CameraReferencePolicyError,
)

router = APIRouter(prefix="/api/centres", tags=["camera-reference-shadow"])


class Proposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reference_digest: str = Field(min_length=64, max_length=64)
    capture_id: str = Field(min_length=1, max_length=128)
    source_review_id: str = Field(min_length=1, max_length=128)
    expected_revision: int = Field(ge=0)


class Review(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(gt=0)
    independent_review_id: str = Field(min_length=1, max_length=128)
    verified_healthy: bool
    verified_same_view: bool
    compared_independently: bool


class Suspension(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(gt=0)
    reason: str = Field(min_length=1, max_length=128)


def _context(request: Request, centre_id: str) -> tuple[OfficerPrincipal, str]:
    # Both checks are essential. Development/demo mode must NOT bypass
    # identity checks. The protected boundary derives the real principal.
    if not (
        os.getenv("KAUSHALWATCH_ENV", "").strip().lower() == "staging"
        and os.getenv("KAUSHALWATCH_CAMERA_REFERENCE_WORKFLOW", "").strip().lower()
            in ("shadow", "shadow_artifact")
        and os.getenv("KAUSHALWATCH_STORAGE_BACKEND", "") == "postgres"
        and os.getenv("KAUSHALWATCH_REVIEW_AUTH_MODE", "") in ("token", "oidc")
    ):
        raise HTTPException(status_code=404, detail="Reference review is unavailable")
    principal = getattr(request.state, "officer_principal", None)
    if not isinstance(principal, OfficerPrincipal):
        raise HTTPException(status_code=401, detail="Authenticated officer session required")
    centre = next((c for c in DEMO_CENTRES if c["centre_id"] == centre_id), None)
    if centre is None or not principal.can_access(centre_id):
        raise HTTPException(status_code=404, detail="Centre not found")
    return principal, str(centre["camera_id"])


def _safe(call):
    try:
        return call()
    except CameraReferenceConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except CameraReferencePolicyError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except Exception:
        # Avoid leaking DB internals, schema names or connection strings.
        raise HTTPException(status_code=503, detail="Reference review temporarily unavailable") from None


@router.get("/{centre_id}/camera-reference")
def read_camera_reference(centre_id: str, request: Request):
    officer, camera = _context(request, centre_id)
    return _safe(lambda: ProtectedCameraReferenceWorkflow().get(
        principal=officer, centre_id=centre_id, camera_id=camera,
    ))


@router.post("/{centre_id}/camera-reference/propose")
def propose_camera_reference(centre_id: str, request: Request, payload: Proposal):
    officer, camera = _context(request, centre_id)
    return _safe(lambda: ProtectedCameraReferenceWorkflow().propose(
        principal=officer, centre_id=centre_id, camera_id=camera,
        reference_digest=payload.reference_digest,
        capture_id=payload.capture_id,
        source_review_id=payload.source_review_id,
        expected_revision=payload.expected_revision,
    ))


@router.post("/{centre_id}/camera-reference/review")
def review_camera_reference(centre_id: str, request: Request, payload: Review):
    officer, camera = _context(request, centre_id)
    return _safe(lambda: ProtectedCameraReferenceWorkflow().review(
        principal=officer, centre_id=centre_id, camera_id=camera,
        expected_revision=payload.expected_revision,
        independent_review_id=payload.independent_review_id,
        verified_healthy=payload.verified_healthy,
        verified_same_view=payload.verified_same_view,
        compared_independently=payload.compared_independently,
    ))


@router.post("/{centre_id}/camera-reference/suspend")
def suspend_camera_reference(centre_id: str, request: Request, payload: Suspension):
    officer, camera = _context(request, centre_id)
    return _safe(lambda: ProtectedCameraReferenceWorkflow().suspend(
        principal=officer, centre_id=centre_id, camera_id=camera,
        expected_revision=payload.expected_revision, reason=payload.reason,
    ))



def _artifact_mode() -> None:
    if os.getenv("KAUSHALWATCH_CAMERA_REFERENCE_WORKFLOW", "") != "shadow_artifact":
        raise HTTPException(status_code=404, detail="Private camera reference images are unavailable")


@router.post("/{centre_id}/camera-reference/attach")
async def attach_camera_reference(
    centre_id: str, request: Request, expected_revision: int,
):
    officer, camera = _context(request, centre_id)
    _artifact_mode()
    from app.services.camera_reference_artifacts import (
        MAX_UPLOAD_BYTES, attach_reference_image,
    )
    if officer.role != "centre_reviewer":
        raise HTTPException(status_code=403, detail="Camera reference upload requires centre reviewer")
    if request.headers.get("content-type", "").split(";")[0].strip().lower() not in (
        "image/png", "image/jpeg",
    ):
        raise HTTPException(status_code=415, detail="Only PNG/JPEG reference images are supported")
    if not 0 < expected_revision <= 2147483647:
        raise HTTPException(status_code=422, detail="Invalid expected reference revision")
    parts = await _bounded_reference_body(request, MAX_UPLOAD_BYTES)
    return _safe(lambda: attach_reference_image(
        principal=officer, centre_id=centre_id, camera_id=camera,
        expected_revision=expected_revision, content=bytes(parts),
    ))


@router.get("/{centre_id}/camera-reference/frame")
def read_private_reference(
    centre_id: str, request: Request, expected_revision: int,
):
    officer, camera = _context(request, centre_id)
    _artifact_mode()
    from app.services.camera_reference_artifacts import verified_reference_frame
    _, encoded = _safe(lambda: verified_reference_frame(
        principal=officer, centre_id=centre_id, camera_id=camera,
        expected_revision=expected_revision,
    ))
    return Response(
        encoded, media_type="image/png",
        headers={
            "Cache-Control": "private, no-store, max-age=0",
            "Content-Security-Policy": "default-src 'none'; sandbox",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": 'inline; filename="review-reference.png"',
        },
    )



async def _bounded_reference_body(request: Request, maximum: int) -> bytes:
    content = bytearray()
    async for chunk in request.stream():
        if len(content) + len(chunk) > maximum:
            raise HTTPException(status_code=413, detail="Reference image exceeds 2 MiB")
        content.extend(chunk)
    return bytes(content)


@router.post("/{centre_id}/camera-reference/propose-image")
async def propose_with_private_image(
    centre_id: str, request: Request, expected_revision: int,
    capture_id: str, source_review_id: str,
):
    officer, camera = _context(request, centre_id)
    _artifact_mode()
    from app.services.camera_reference_artifacts import (
        MAX_UPLOAD_BYTES, attach_reference_image, normalize_image,
    )
    if officer.role != "centre_reviewer":
        raise HTTPException(status_code=403, detail="Reference proposals require a centre reviewer")
    if request.headers.get("content-type", "").split(";")[0].strip().lower() not in (
        "image/png", "image/jpeg",
    ):
        raise HTTPException(status_code=415, detail="Only PNG/JPEG reference images are supported")
    if not 0 <= expected_revision <= 2147483647:
        raise HTTPException(status_code=422, detail="Invalid reference revision")
    body = await _bounded_reference_body(request, MAX_UPLOAD_BYTES)
    def execute():
        _, _, pixel_sha, _ = normalize_image(body)
        workflow = ProtectedCameraReferenceWorkflow()
        proposed = workflow.propose(
            principal=officer, centre_id=centre_id, camera_id=camera,
            reference_digest=pixel_sha,
            capture_id=capture_id, source_review_id=source_review_id,
            expected_revision=expected_revision,
        )
        attach_reference_image(
            principal=officer, centre_id=centre_id, camera_id=camera,
            expected_revision=proposed["revision"], content=body,
        )
        return workflow.get(principal=officer, centre_id=centre_id, camera_id=camera)
    return _safe(execute)
