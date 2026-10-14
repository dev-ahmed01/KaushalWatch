"""Produce a read-only evidence reconciliation report; never deletes objects."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.services.evidence_inventory import audit_private_evidence


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only private evidence inventory audit")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--limit", type=int, default=50000)
    args = parser.parse_args()
    target = args.out.expanduser().resolve()
    if target.exists():
        parser.error("Refusing to replace an existing inventory report")
    try:
        report = audit_private_evidence(limit=args.limit)
    except Exception as exc:
        # Do not reveal a credential-bearing object-store/DB error to logs.
        print(f"Inventory could not complete: {type(exc).__name__}", file=sys.stderr)
        raise SystemExit(2) from None

    target.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(json.dumps({
        "status": report["status"], "read_only": True, "completed": True,
        "report_created": True, "findings": report["findings"],
    }))
    if report["status"] != "consistent":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
