"""Static frontend-to-backend route contract gate for the SIH release.

This catches accidental path/method drift at review time. It does NOT prove
runtime availability, response schema correctness, authorization, or model
accuracy; those require API and browser integration tests.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND_FILE = ROOT / "backend" / "app" / "main.py"
FRONTEND_FILE = ROOT / "web" / "app" / "lib" / "api.ts"

# Name, HTTP method and FastAPI route. Keep the important officer-facing
# read/write paths explicit; accidental deletion from both sides must fail.
REQUIRED_CONTRACTS = (
    ("getActionQueue", "GET", "/api/actions"),
    ("getNetworkInsights", "GET", "/api/insights"),
    ("getKaushalBrief", "GET", "/api/kaushalai/brief"),
    ("getCentres", "GET", "/api/centres"),
    ("getActivityIntelligence", "GET", "/api/centres/{centre_id}/activity-intelligence"),
    ("getCentreIntelligence", "GET", "/api/centres/{centre_id}/intelligence"),
    ("getCentre", "GET", "/api/centres/{centre_id}"),
    ("getDashboard", "GET", "/api/dashboard"),
    ("getHistory", "GET", "/api/analysis-history"),
    ("getCases", "GET", "/api/cases"),
    ("getReviewAccess", "GET", "/api/review-access"),
    ("getEvidencePack", "GET", "/api/cases/{case_id}/evidence-pack"),
    ("reviewCase", "POST", "/api/cases/{case_id}/review"),
    ("askAssistant", "POST", "/api/assistant/chat"),
    ("getAssistantStatus", "GET", "/api/assistant/status"),
    ("transcribeAssistantAudio", "POST", "/api/assistant/transcribe"),
    ("synthesizeAssistantSpeech", "POST", "/api/assistant/speech"),
    ("getSettings", "GET", "/api/centres/{centre_id}/settings"),
    ("saveSettings", "PUT", "/api/centres/{centre_id}/settings"),
    ("getRuntimeReadiness", "GET", "/api/runtime-readiness"),
    ("reportUrl", "GET", "/api/centres/{centre_id}/report"),
    ("reportPdfUrl", "GET", "/api/centres/{centre_id}/report.pdf"),
)

FUNCTION_RE = re.compile(r"^export (?:async )?function (?P<name>\w+)\(", re.MULTILINE)
TEMPLATE_RE = re.compile(r"`\$\{API\}([^`]+)`")
PARAM_RE = re.compile(r"\$\{encodeURIComponent\((\w+)\)\}")
METHOD_RE = re.compile(r"method:\s*['\"]([A-Z]+)['\"]")


def _snake_case(value: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", value).lower()


def frontend_contracts(source: str) -> dict[str, tuple[str, str]]:
    """Extract exported API helpers and their first `${API}` route.

    Deliberately restrict to the small, inspectable conventions in api.ts.
    Unsupported helper shapes fail the required-contract checks, rather
    than being silently assumed compatible.
    """
    functions = list(FUNCTION_RE.finditer(source))
    routes: dict[str, tuple[str, str]] = {}
    for index, match in enumerate(functions):
        end = functions[index + 1].start() if index + 1 < len(functions) else len(source)
        body = source[match.end():end]
        url = TEMPLATE_RE.search(body)
        if not url:
            continue
        path = url.group(1).split("?", 1)[0]
        path = PARAM_RE.sub(lambda part: "{" + _snake_case(part.group(1)) + "}", path)
        method_match = METHOD_RE.search(body)
        method = method_match.group(1) if method_match else "GET"
        routes[match.group("name")] = (method, path)
    return routes


def backend_contracts(source: str) -> set[tuple[str, str]]:
    """Extract literal FastAPI method/path decorators without importing the app."""
    routes: set[tuple[str, str]] = set()
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            func = decorator.func
            if not (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and func.value.id == "app"
                and func.attr in {"get", "post", "put", "patch", "delete"}
                and decorator.args
                and isinstance(decorator.args[0], ast.Constant)
                and isinstance(decorator.args[0].value, str)
            ):
                continue
            routes.add((func.attr.upper(), decorator.args[0].value))
    return routes


def contract_errors(backend_source: str, frontend_source: str) -> list[str]:
    server = backend_contracts(backend_source)
    client = frontend_contracts(frontend_source)
    errors: list[str] = []
    for name, method, route in REQUIRED_CONTRACTS:
        actual = client.get(name)
        if actual != (method, route):
            errors.append(
                f"frontend {name}: expected {method} {route}; got {actual!r}"
            )
        if (method, route) not in server:
            errors.append(f"backend missing {method} {route}")
    return errors


def main() -> None:
    errors = contract_errors(
        BACKEND_FILE.read_text(encoding="utf-8"),
        FRONTEND_FILE.read_text(encoding="utf-8"),
    )
    if errors:
        print("SIH frontend/backend route contract check FAILED:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print(
        f"SIH frontend/backend route contract check passed: "
        f"{len(REQUIRED_CONTRACTS)} required method/path contracts."
    )
    print("Runtime response, permissions and evidence claims require separate E2E checks.")


if __name__ == "__main__":
    main()
