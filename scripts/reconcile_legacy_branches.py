"""One-time, SHA-locked archival of reconciled legacy KaushalWatch heads.

Divergent commits are NEVER claimed merged. Every tip is first retained under
an immutable archive tag, after which superseded PRs may be closed and their
branch refs removed. Camera Trust remains untouched. CI errors fail closed.
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

REPOSITORY = "dev-ahmed01/KaushalWatch"
ARCHIVE = "archive/reconciled-20261014/"
# Reviewed SHA tips as inventoried after PR #53/#55 integration into main.
AUDITED = {
    "agile/auditability-cycle-8": "ed74ddf61ff52a094a24685d4874f3a8c01323b3",
    "agile/demo-operations-cycle-4": "1b93a93814c546337b00c5e41bdd18c33d6b2af6",
    "agile/product-clarity-cycle-2": "f34dc99a663d46f62bc193d81acc0861379d0ceb",
    "audit/full-ui-visual-check": "50281faec1c82498793860c939ed9298231db7f9",
    "cycle/grounding-cache-hardening": "025cde25227aaf913b2f58711d153be4e9aa9355",
    "cycle/operability-window": "30ad45d92816d3a4de8cff3cbf5114f851cc748f",
    "experiment/dod-grounding-review": "f04a2a9065c7539fab257d96b705f1d9a0a2100e",
    "feature/free-ai-providers": "c1c89c4082e2f878480eb236f5adf70b6eedd4b4",
    "redesign/full-command-centre-v3": "cea62dcf0ffa9888a2cb2a301f4cb75c948ee705",
    "redesign/portfolio-review-report-v3": "ead15557e6c79796fcd3c1c7de136a1f670a67b3",
    "redesign/product-v2-polish": "9f16d66c140c270c1c1a2c5a4e3bdeb40c0cf4b2",
}
SUPERSEDED_PRS = {
    25: "agile/auditability-cycle-8",
    31: "redesign/full-command-centre-v3",
    34: "redesign/portfolio-review-report-v3",
}
SAFE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
HEX = re.compile(r"^[0-9a-f]{40}$")
PRESERVE = "fix/uhctd-camera-trust-v2"


def audit_config() -> None:
    assert set(SUPERSEDED_PRS.values()) <= set(AUDITED)
    assert not set(AUDITED) & {"main", PRESERVE}
    if len(AUDITED) != len(set(AUDITED)):
        raise ValueError("Duplicate audited branch")
    for name, sha in AUDITED.items():
        if (not SAFE.fullmatch(name) or ".." in name or "//" in name
            or ".lock" in name or not HEX.fullmatch(sha)):
            raise ValueError("Unsafe branch or tip in fixed allowlist")


def can_prune(name: str, actual_sha: str, *, protected: bool, open_heads: set[str],
              tag_sha: str | None) -> bool:
    """Delete only unchanged, archived, no-longer-open and not-protected heads."""
    return (name in AUDITED and name not in {"main", PRESERVE}
            and actual_sha == AUDITED[name] and not protected
            and name not in open_heads and tag_sha == actual_sha)


class Github:
    def __init__(self, token: str):
        if not token:
            raise ValueError("Missing GitHub Actions token")
        self.root = "https://api.github.com/repos/" + REPOSITORY
        self.headers = {
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def call(self, method: str, suffix: str, data=None):
        url = self.root + ("/" + suffix if suffix else "")
        payload = json.dumps(data).encode() if data is not None else None
        headers = dict(self.headers)
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=payload, method=method, headers=headers)
        with urllib.request.urlopen(req, timeout=25) as resp:
            value = resp.read()
        return json.loads(value) if value else None

    def branch(self, name: str) -> dict:
        return self.call("GET", "branches/" + urllib.parse.quote(name, safe="/"))

    def main_sha(self) -> str:
        return self.branch("main")["commit"]["sha"]

    def tag_sha(self, name: str) -> str | None:
        tag = ARCHIVE + name
        path = "git/ref/tags/" + urllib.parse.quote(tag, safe="/")
        try:
            ref = self.call("GET", path)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            raise
        if ref["ref"] != "refs/tags/" + tag or ref["object"]["type"] != "commit":
            raise ValueError("Archive ref is not a lightweight commit tag")
        return ref["object"]["sha"]

    def archive(self, name: str, sha: str) -> None:
        if self.tag_sha(name) is None:
            try:
                self.call("POST", "git/refs", {
                    "ref": "refs/tags/" + ARCHIVE + name,
                    "sha": sha,
                })
            except urllib.error.HTTPError as exc:
                if exc.code != 422:
                    raise
        if self.tag_sha(name) != sha:
            raise ValueError("Archive SHA mismatch: refusing to prune")

    def open_heads(self) -> set[str]:
        heads = set()
        for page in range(1, 7):
            pulls = self.call("GET", "pulls?state=open&per_page=100&page=" + str(page))
            if not isinstance(pulls, list):
                raise ValueError("Invalid open PR inventory")
            for pull in pulls:
                if (pull.get("head", {}).get("repo") or {}).get("full_name") == REPOSITORY:
                    heads.add(pull["head"]["ref"])
            if len(pulls) < 100:
                return heads
        raise ValueError("Open PR inventory was truncated")

    def supersede_pr(self, number: int, branch: str, sha: str) -> None:
        pr = self.call("GET", "pulls/" + str(number))
        if pr.get("merged") or pr["head"]["ref"] != branch or pr["head"]["sha"] != sha:
            raise ValueError("PR head changed or was merged; cannot close as superseded")
        if pr["state"] == "closed":
            return
        if pr["state"] != "open":
            raise ValueError("Unknown PR state")
        note = (
            "Closed as superseded during KaushalWatch Phase 3A branch reconciliation. "
            "Not merged: the current main uses the newer protected, route-based "
            "implementation, and this historic PR has unresolved review feedback. "
            "The exact source tip is preserved at refs/tags/" + ARCHIVE + branch
            + " (" + sha + "). This preserves recoverability without automatically "
            "importing outdated behavior."
        )
        self.call("POST", f"issues/{number}/comments", {"body": note})
        self.call("PATCH", f"pulls/{number}", {"state": "closed"})


def execute(expected: str, *, dry_run: bool = True) -> dict:
    audit_config()
    api = Github(os.getenv("GITHUB_TOKEN", ""))
    if api.call("GET", "")["default_branch"] != "main":
        raise ValueError("Unexpected default branch")
    if api.main_sha() != expected:
        raise ValueError("Main has advanced; restarting from new audited base required")
    present = set()
    # Preflight ALL branches before mutating any state. An already archived,
    # deleted exact tip is acceptable on a retry after an interrupted run.
    for name, sha in AUDITED.items():
        try:
            info = api.branch(name)
        except urllib.error.HTTPError as exc:
            if exc.code != 404 or api.tag_sha(name) != sha:
                raise
            continue
        if info["commit"]["sha"] != sha or info.get("protected"):
            raise ValueError("Audited head moved or is protected: " + name)
        present.add(name)
    for number, name in SUPERSEDED_PRS.items():
        pr = api.call("GET", f"pulls/{number}")
        if pr["head"]["ref"] != name or pr["head"]["sha"] != AUDITED[name] or pr.get("merged"):
            raise ValueError("Open legacy PR changed: " + str(number))
        if pr["state"] not in {"open", "closed"}:
            raise ValueError("Unknown PR state")

    if dry_run:
        return {"mode": "dry_run", "ready": list(AUDITED), "closed_prs": [],
                "deleted": [], "preserved": [PRESERVE, "main"]}

    archived, closed, deleted, errors = [], [], [], []
    # Archive each tip first. Do not close or delete ANY branch until every
    # snapshot is durable under a verified immutable tag.
    for name, sha in AUDITED.items():
        api.archive(name, sha)
        archived.append(name)
    if api.main_sha() != expected:
        raise ValueError("Main advanced during archival; archived refs retained")
    for number, name in SUPERSEDED_PRS.items():
        api.supersede_pr(number, name, AUDITED[name])
        closed.append(number)
    open_heads = api.open_heads()
    if api.main_sha() != expected:
        raise ValueError("Main advanced before deletion; no refs pruned")
    for name, sha in AUDITED.items():
        try:
            if name not in present:
                if api.tag_sha(name) != sha:
                    raise ValueError("Missing branch has no validated archive")
                continue
            info = api.branch(name)
            tag = api.tag_sha(name)
            if not can_prune(name, info["commit"]["sha"],
                             protected=info["protected"], open_heads=open_heads, tag_sha=tag):
                raise ValueError("Protection, live PR or SHA check failed")
            if api.main_sha() != expected:
                raise ValueError("Main advanced while pruning")
            api.call("DELETE", "git/refs/heads/" + urllib.parse.quote(name, safe="/"))
            deleted.append(name)
        except (urllib.error.HTTPError, ValueError, KeyError) as exc:
            entry = {"branch": name, "type": type(exc).__name__}
            if isinstance(exc, urllib.error.HTTPError):
                entry["http_status"] = exc.code
            errors.append(entry)
    report = {"mode": "archived_legacy_pruned", "main_sha": expected,
              "archive_prefix": ARCHIVE, "archived": archived,
              "closed_prs": closed, "deleted": deleted,
              "preserved": [PRESERVE, "main"], "errors": errors}
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--expected-main-sha", required=True)
    p.add_argument("--execute", action="store_true")
    args = p.parse_args()
    if not HEX.fullmatch(args.expected_main_sha):
        p.error("Invalid expected main SHA")
    try:
        report = execute(args.expected_main_sha, dry_run=not args.execute)
        print(json.dumps(report, indent=2))
        summary = os.getenv("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a", encoding="utf-8") as file:
                file.write(
                    "\n## Phase 3A: legacy branch reconciliation\n"
                    f"Archived: **{len(report.get('archived', []))}**; "
                    f"closed PRs: **{len(report['closed_prs'])}**; "
                    f"pruned: **{len(report['deleted'])}**; "
                    f"errors: **{len(report.get('errors', []))}**.\n"
                )
        if report.get("errors"):
            raise SystemExit(1)
    except (ValueError, urllib.error.HTTPError, KeyError, OSError) as exc:
        # No token, private request detail or environment values in logs.
        print("Audited cleanup blocked: " + type(exc).__name__, file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
