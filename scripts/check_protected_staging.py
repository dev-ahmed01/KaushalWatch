"""Public-only protected deployment preflight, with no privileged credentials.

Checks live HTTP contracts without accessing private evidence, writing cases,
or crossing an IdP login. CI loopback is ALWAYS labelled synthetic/nonqualifying.
Run against actual HTTPS staging before operator acceptance.
"""
from __future__ import annotations

import argparse
import json
from urllib.parse import urlsplit

import httpx


def origin(value: str, *, synthetic: bool) -> str:
    try:
        u = urlsplit(value)
        loopback = u.scheme == "http" and u.hostname == "127.0.0.1"
        if ((u.scheme != "https" and not (synthetic and loopback))
                or not u.hostname or u.username or u.password or u.path not in {"", "/"}
                or u.query or u.fragment):
            raise ValueError()
    except (ValueError, TypeError):
        raise ValueError("Expected a bare HTTPS origin; synthetic mode permits loopback") from None
    return f"{u.scheme}://{u.netloc}"


def run_check(api: str, web: str, *, synthetic: bool) -> dict:
    api, web = origin(api, synthetic=synthetic), origin(web, synthetic=synthetic)
    checks: dict[str, bool] = {}
    with httpx.Client(follow_redirects=False, timeout=8.0, trust_env=False) as client:
        def fetch(base: str, path: str):
            return client.get(base + path, headers={"Accept": "application/json"})

        ready = fetch(api, "/api/ready")
        checks["database_readiness_endpoint"] = (
            ready.status_code == 200 and ready.json() == {"ready": True}
            and "no-store" in ready.headers.get("cache-control", "")
        )
        health = fetch(api, "/api/health")
        checks["separate_liveness"] = health.status_code == 200
        auth = fetch(api, "/api/review-access")
        checks["oidc_api_mode"] = (auth.status_code == 200
            and auth.json() == {"mode": "oidc", "required": True, "prototype_only": False})
        forbidden = fetch(api, "/api/cases")
        checks["api_anonymous_read_denied"] = (
            forbidden.status_code == 401 and
            "Bearer" in forbidden.headers.get("www-authenticate", "")
        )
        headers = fetch(web, "/api/auth/status")
        status = headers.json() if headers.status_code == 200 else {}
        checks["browser_oidc_mode"] = (status.get("mode") == "protected"
            and status.get("identityMode") == "oidc"
            and status.get("authenticated") is False
            and "no-store" in headers.headers.get("cache-control", ""))
        browser = fetch(web, "/api/proxy/api/cases")
        checks["browser_anonymous_proxy_denied"] = browser.status_code == 401
        sso = fetch(web, "/api/auth/oidc/start")
        location = sso.headers.get("location", "")
        cookies = sso.headers.get("set-cookie", "").lower()
        checks["sso_redirect_with_protected_cookie"] = (
            sso.status_code == 303 and
            location.startswith("https://" if not synthetic else "http://127.0.0.1:")
            and "state=" in location and "code_challenge=" in location
            and "code_challenge_method=S256" in location
            and "kw_oidc_transaction=" in cookies and "httponly" in cookies
            and "max-age=300" in cookies
            and (synthetic or "secure" in cookies)
        )
    return {
        "status": "synthetic_transport_check_only" if synthetic else (
            "public_preflight_passed" if all(checks.values()) else "preflight_blocked"
        ),
        "passed": all(checks.values()),
        "real_cloud_certified": False,
        "checks": checks,
        "not_tested": [
            "IdP MFA and authentication policy",
            "AWS IAM / bucket public access / real KMS",
            "Media and SQL disaster recovery under actual infrastructure failure",
            "Independent real-camera accuracy",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="No-secret read-only staging preflight")
    parser.add_argument("--api", required=True, help="Bare protected API origin")
    parser.add_argument("--web", required=True, help="Bare protected browser origin")
    parser.add_argument("--synthetic-loopback", action="store_true")
    args = parser.parse_args()
    try:
        report = run_check(args.api, args.web, synthetic=args.synthetic_loopback)
    except (ValueError, httpx.HTTPError, json.JSONDecodeError) as exc:
        report = {
            "status": "preflight_blocked", "passed": False, "real_cloud_certified": False,
            "reason": type(exc).__name__,
        }
    print(json.dumps(report, indent=2))
    if not report["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
