"""Archive and prune only *verified merged-PR head refs*.

No force pushes. Every ref gets an immutable SHA-addressed archival tag first.
Default is dry-run. A branch with an open PR, unknown history, or a tip that
differs from its merged PR head is never deleted.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

SAFE_REF = re.compile(r"^[A-Za-z0-9._/-]{1,200}$")
ALWAYS_KEEP = frozenset({
    "main", "fix/uhctd-camera-trust-v2",
})


def safe_ref(value: str) -> bool:
    return (
        isinstance(value, str) and bool(SAFE_REF.fullmatch(value))
        and not value.startswith((".", "/", "-"))
        and not value.endswith((".", "/"))
        and ".." not in value and "//" not in value
        and "@{" not in value and ".lock" not in value
    )


def select_branches(branches: list, pull_requests: list, repo: str, default: str) -> tuple[list, list]:
    """Choose only heads whose exact SHA is the head of a *merged* same-repo PR."""
    open_heads = {
        p["head"]["ref"] for p in pull_requests
        if p.get("state") == "open" and p.get("head")
        and (p["head"].get("repo") or {}).get("full_name") == repo
    }
    merged = {}
    for p in pull_requests:
        head = p.get("head") or {}
        if p.get("merged_at") and (head.get("repo") or {}).get("full_name") == repo:
            merged.setdefault(head.get("ref"), set()).add(head.get("sha"))
    selected, skipped = [], []
    for branch in branches:
        name = branch.get("name")
        sha = (branch.get("commit") or {}).get("sha")
        reason = None
        if not safe_ref(name):
            reason = "unsafe-name"
        elif name == default or name in ALWAYS_KEEP:
            reason = "protected-by-policy"
        elif branch.get("protected"):
            reason = "GitHub-protected"
        elif name in open_heads:
            reason = "open-PR"
        elif not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}", sha):
            reason = "missing-tip"
        elif sha not in merged.get(name, set()):
            reason = "no-exact-merged-PR-head"
        if reason:
            skipped.append({"branch": name, "reason": reason})
        else:
            selected.append({"branch": name, "sha": sha})
    return selected, skipped


class GitHub:
    def __init__(self, repo: str, token: str):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
            raise ValueError("Invalid fixed GitHub repository")
        if not token:
            raise ValueError("GITHUB_TOKEN missing")
        self.base = "https://api.github.com/repos/" + repo
        self.headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": "Bearer " + token,
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def request(self, method: str, path: str, payload=None):
        url = self.base + ("/" + path if path else "")
        headers = dict(self.headers)
        body = None
        if payload is not None:
            body = json.dumps(payload).encode()
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, method=method, headers=headers, data=body)
        with urllib.request.urlopen(req, timeout=20) as response:
            raw = response.read()
        return json.loads(raw) if raw else {}

    def collection(self, name: str) -> list:
        rows = []
        for page in range(1, 20):
            sep = "&" if "?" in name else "?"
            data = self.request("GET", f"{name}{sep}per_page=100&page={page}")
            if not isinstance(data, list):
                raise ValueError("Unexpected GitHub collection schema")
            rows.extend(data)
            if len(data) < 100:
                return rows
        raise ValueError("Refusing truncated GitHub branch/PR inventory")

    def exact_branch_sha(self, name: str) -> str:
        branch = self.request("GET", "branches/" + urllib.parse.quote(name, safe="/"))
        if branch.get("protected"):
            raise ValueError("Branch became protected during cleanup")
        return branch["commit"]["sha"]

    def archive(self, name: str, sha: str) -> None:
        tag = "archive/merged-branches/" + name
        ref = "refs/tags/" + tag
        urlref = "git/ref/tags/" + urllib.parse.quote(tag, safe="/")
        try:
            existing = self.request("GET", urlref)
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
            existing = None
        if existing is None:
            try:
                self.request("POST", "git/refs", {"ref": ref, "sha": sha})
            except urllib.error.HTTPError as exc:
                # Another run may have created a tag; verify the actual ref
                # before proceeding. Never overwrite or force-move a tag.
                if exc.code != 422:
                    raise
        confirmed = self.request("GET", urlref)
        if (confirmed.get("ref") != ref
            or (confirmed.get("object") or {}).get("sha") != sha):
            raise ValueError("Archival tag does not pin the exact branch tip")

    def delete(self, name: str) -> None:
        self.request("DELETE", "git/refs/heads/" + urllib.parse.quote(name, safe="/"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Archive and prune exact merged-PR heads only")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--expected-main-sha", required=True)
    parser.add_argument("--execute", action="store_true", help="Requires write-capable GitHub token")
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.expected_main_sha):
        parser.error("Expected a pinned main SHA")
    gh = GitHub(args.repo, os.getenv("GITHUB_TOKEN", ""))
    info = gh.request("GET", "")
    default = info.get("default_branch")
    if default != "main" or gh.exact_branch_sha("main") != args.expected_main_sha:
        raise ValueError("Main ref changed or repository default is not main")
    branches = gh.collection("branches")
    prs = gh.collection("pulls?state=all")
    selected, skipped = select_branches(branches, prs, args.repo, default)
    deleted, failed = [], []
    for item in selected:
        name, sha = item["branch"], item["sha"]
        if not args.execute:
            continue
        try:
            if gh.exact_branch_sha("main") != args.expected_main_sha:
                raise ValueError("Main changed during cleanup")
            if gh.exact_branch_sha(name) != sha:
                raise ValueError("Branch moved before archival/deletion")
            gh.archive(name, sha)
            if gh.exact_branch_sha(name) != sha:
                raise ValueError("Branch moved after archival; not deleted")
            gh.delete(name)
            deleted.append(name)
        except (urllib.error.HTTPError, ValueError, KeyError, TimeoutError) as exc:
            # No blind retries or force pushes. Record a safe error code only,
            # never response headers, token values or private API bodies.
            reason = {"branch": name, "type": type(exc).__name__}
            if isinstance(exc, urllib.error.HTTPError):
                reason["http_status"] = exc.code
            failed.append(reason)
    result = {
        "mode": "archived_and_pruned" if args.execute else "dry_run",
        "base_sha": args.expected_main_sha,
        "selected_merged_pr_heads": selected,
        "deleted_after_archival": deleted,
        "skipped_count": len(skipped),
        "skipped": skipped,
        "failures": failed,
    }
    print(json.dumps(result, indent=2))
    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as out:
            out.write(
                "\n## Safe historical-branch archival and cleanup\n"
                f"Mode: **{result['mode']}**. "
                f"Archived and deleted: **{len(deleted)}**; "
                f"not eligible: **{len(skipped)}**; "
                f"failures: **{len(failed)}**.\n\n"
            )
            for row in failed:
                out.write(f"- Failure: `{row['branch']}` ({row['type']})\n")
            for name in deleted:
                out.write(f"- Archived then pruned: `{name}`\n")
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, urllib.error.HTTPError, OSError, KeyError) as exc:
        print("Safe branch cleanup blocked: " + type(exc).__name__, file=sys.stderr)
        raise SystemExit(2)
