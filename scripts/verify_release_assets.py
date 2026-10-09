"""Validate frozen local demonstration assets without uploading them."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.release_assets import qualify_release_assets


def main() -> None:
    parser = argparse.ArgumentParser(description="Fail-closed SIH release media/annotation qualification")
    parser.add_argument(
        "--manifest",
        default=os.getenv("KAUSHALWATCH_RELEASE_ASSET_MANIFEST"),
        help="Local JSON manifest (e.g. data/annotations/release-assets.json).",
    )
    args = parser.parse_args()
    if not args.manifest:
        print(json.dumps({
            "ready": False,
            "checks": [{"check": "asset_manifest", "ok": False,
                        "detail": "Supply --manifest or KAUSHALWATCH_RELEASE_ASSET_MANIFEST"}],
            "claim_boundary": "No final-media claims.",
        }, indent=2))
        raise SystemExit(2)
    report = qualify_release_assets(Path(args.manifest))
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["ready"] else 2)


if __name__ == "__main__":
    main()
