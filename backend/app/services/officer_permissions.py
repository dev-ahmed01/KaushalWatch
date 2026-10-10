"""Server-enforced officer centre permissions for protected deployments.

This is a configuration-backed prototype identity policy, not full RBAC/IdP.
Unknown role, centre, actor or missing mapping fails closed.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os

from fastapi import HTTPException, Request

from app.services.review_access import LOCAL_ENVS, _configuration

ROLES = frozenset({"network_admin", "centre_reviewer", "centre_viewer"})


@dataclass(frozen=True)
class OfficerPrincipal:
    actor: str
    role: str
    centres: frozenset[str]

    @property
    def is_admin(self) -> bool:
        return self.role == "network_admin"

    @property
    def can_write(self) -> bool:
        return self.role in {"network_admin", "centre_reviewer"}

    def can_access(self, centre_id: str) -> bool:
        return self.is_admin or centre_id in self.centres


def _configuration_error() -> HTTPException:
    return HTTPException(status_code=503, detail="Officer centre permissions are not securely configured.")


def configured_principals() -> dict[str, OfficerPrincipal]:
    mode, tokens = _configuration()
    if mode != "token":
        raise _configuration_error()
    try:
        raw = json.loads(os.environ.get("KAUSHALWATCH_OFFICER_PERMISSIONS_JSON", ""))
    except (ValueError, TypeError):
        raise _configuration_error() from None
    if not isinstance(raw, dict) or set(raw) != set(tokens):
        raise _configuration_error()

    from app.services.demo_network import DEMO_CENTRES
    valid_centres = {c["centre_id"] for c in DEMO_CENTRES}
    result: dict[str, OfficerPrincipal] = {}
    for actor, spec in raw.items():
        if not isinstance(spec, dict) or set(spec) != {"role", "centres"}:
            raise _configuration_error()
        role, centres = spec["role"], spec["centres"]
        if role not in ROLES or not isinstance(centres, list):
            raise _configuration_error()
        if len(centres) != len(set(str(c) for c in centres)):
            raise _configuration_error()
        if not all(isinstance(c, str) and c in valid_centres for c in centres):
            raise _configuration_error()
        # No magic '*' wildcard: network-wide access requires an explicit
        # network_admin role, while centre roles need concrete assignments.
        if (role == "network_admin" and centres) or (role != "network_admin" and not centres):
            raise _configuration_error()
        result[actor] = OfficerPrincipal(actor, role, frozenset(centres))
    return result


def request_principal(request: Request) -> OfficerPrincipal | None:
    """Return None ONLY for explicit local demo mode; protected mode never falls back."""
    if os.getenv("KAUSHALWATCH_ENV", "development").strip().lower() in LOCAL_ENVS:
        return None
    principal = getattr(request.state, "officer_principal", None)
    if not isinstance(principal, OfficerPrincipal):
        raise _configuration_error()
    return principal


def require_centre(request: Request, centre_id: str, *, write: bool = False) -> None:
    principal = request_principal(request)
    if principal is None:
        return
    if not principal.can_access(centre_id):
        # Hide existence to avoid centre enumeration.
        raise HTTPException(status_code=404, detail="Centre not found")
    if write and not principal.can_write:
        raise HTTPException(status_code=403, detail="Officer cannot modify centre data")


def require_write(request: Request) -> None:
    principal = request_principal(request)
    if principal is not None and not principal.can_write:
        raise HTTPException(status_code=403, detail="Officer has read-only access")


def visible(request: Request, rows: list, *, id_attr: str = "centre_id") -> list:
    principal = request_principal(request)
    if principal is None or principal.is_admin:
        return rows
    def cid(row):
        return row.get(id_attr) if isinstance(row, dict) else getattr(row, id_attr, None)
    return [row for row in rows if cid(row) in principal.centres]


def evidence_centre(evidence_id: str) -> str | None:
    # Lazy reference avoids a module import cycle and honors the active store
    # patched by isolated API tests.
    import app.main as main
    for case in main.STORE.list():
        if any(record.evidence_id == evidence_id for record in case.evidence):
            return case.centre_id
    return None
