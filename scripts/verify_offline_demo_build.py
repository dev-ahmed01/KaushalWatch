"""Refuse to launch an unbound/stale Next.js local offline presentation build.

A build receipt proves local source/config linkage, NOT external legitimacy,
institutional field accuracy, browser performance or font licensing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

SCHEMA = "KW_LOCAL_OFFLINE_NEXT_BUILD_V1"
MODE = "CONTROLLED_LOCAL_PROCEDURAL_DEMO_ONLY"
HEXSHA = re.compile(r"[a-f0-9]{40}\Z")
HASH256 = re.compile(r"[a-f0-9]{64}\Z")
BUILD_ID = re.compile(r"[A-Za-z0-9_-]{8,200}\Z")
REQUIRED = {
    "schema", "mode", "commit", "api_origin", "next_build_id",
    "source_manifest_sha256", "runtime_font_requests_external",
    "protected_officer_mode_enabled",
}


class OfflineBuildError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(65536), b""):
            result.update(block)
    return result.hexdigest()


def _read_bounded(path: Path, limit: int) -> bytes:
    if path.is_symlink() or not path.is_file() or not 1 <= path.stat().st_size <= limit:
        raise OfflineBuildError("Offline build source missing or linked")
    return path.read_bytes()


def _unique_pairs(pairs):
    result = {}
    for k, v in pairs:
        if k in result:
            raise OfflineBuildError("Duplicate offline release property")
        result[k] = v
    return result


def verify(root: Path, commit: str, api_port: int) -> dict:
    root = root.expanduser().resolve()
    if not HEXSHA.fullmatch(commit):
        raise OfflineBuildError("Expected exact lowercase source commit")
    if not isinstance(api_port, int) or not 1024 <= api_port <= 65535:
        raise OfflineBuildError("Invalid local API port")
    folder = root / "web" / ".next"
    build_id = _read_bounded(folder / "BUILD_ID", 255).decode("ascii").strip()
    manifest = root / "web" / "public" / "camera-trust" / "manifest.json"
    receipt_bytes = _read_bounded(folder / "kw-offline-demo-build.json", 4096)
    if not BUILD_ID.fullmatch(build_id):
        raise OfflineBuildError("Invalid Next.js build identity")
    if manifest.is_symlink() or not manifest.is_file():
        raise OfflineBuildError("Procedural source manifest missing")
    try:
        payload = json.loads(receipt_bytes, object_pairs_hook=_unique_pairs)
    except OfflineBuildError:
        # A duplicate key is an explicit integrity violation; preserve its
        # diagnosis instead of obscuring it as generic malformed JSON.
        raise
    except (ValueError, UnicodeDecodeError) as exc:
        raise OfflineBuildError("Invalid offline release receipt") from exc
    if not isinstance(payload, dict) or set(payload) != REQUIRED:
        raise OfflineBuildError("Invalid offline release receipt schema")
    if not isinstance(payload["source_manifest_sha256"], str) or not HASH256.fullmatch(payload["source_manifest_sha256"]):
        raise OfflineBuildError("Invalid source manifest fingerprint")
    if (payload["schema"] != SCHEMA or payload["mode"] != MODE
            or payload["commit"] != commit
            or payload["next_build_id"] != build_id
            or payload["api_origin"] != f"http://127.0.0.1:{api_port}"
            or payload["source_manifest_sha256"] != sha256_file(manifest)
            or payload["runtime_font_requests_external"] is not False
            or payload["protected_officer_mode_enabled"] is not False):
        raise OfflineBuildError("Offline build is stale, mismatched or unsupported")
    return {
        "status": "local_prebuilt_next_source_config_verified",
        "source_commit": commit,
        "api_origin": payload["api_origin"],
        "next_build_id": build_id,
        "procedural_manifest_bound": True,
        "field_accuracy_qualified": False,
        "browser_rehearsal_passed": False,
        "runtime_external_requests_independently_verified": False,
    }


def clean_source_commit(root: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True, timeout=10,
        )
        dirty = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=no"],
            check=True, capture_output=True, text=True, timeout=10,
        )
    except (subprocess.CalledProcessError, OSError, subprocess.TimeoutExpired) as exc:
        raise OfflineBuildError("Git source revision unavailable") from exc
    commit = proc.stdout.strip()
    if dirty.stdout.strip() or not HEXSHA.fullmatch(commit):
        raise OfflineBuildError("Cannot use uncommitted source for frozen judge build")
    return commit


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail-closed offline Next.js build identity")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--api-port", type=int, default=8000)
    args = parser.parse_args()
    try:
        sha = clean_source_commit(args.root)
        print(json.dumps({"ready": True, **verify(args.root, sha, args.api_port)}))
    except (OSError, ValueError, TypeError, UnicodeError) as exc:
        print(json.dumps({
            "ready": False,
            "status": "BLOCKED_STALE_OR_INVALID_LOCAL_BUILD",
            "field_accuracy_qualified": False,
            "reason": str(exc)[:200],
        }))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
