from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "data"

MUTABLE_FILES = (
    "cases.json",
    "analysis_history.json",
    "centre_settings.json",
    "edge_events.json",
    "evidence_index.json",
)
MUTABLE_DIRS = ("evidence",)


def reset_demo_state(data_dir: Path) -> dict[str, Any]:
    """Remove only mutable runtime demo state.

    Raw footage, manifests, reviewed detector caches and other demo assets are
    intentionally outside this allowlist and are never touched.
    """
    data_dir = data_dir.resolve()
    removed: list[str] = []
    already_clean: list[str] = []

    data_dir.mkdir(parents=True, exist_ok=True)

    for name in MUTABLE_FILES:
        path = data_dir / name
        if path.exists():
            path.unlink()
            removed.append(str(path))
        else:
            already_clean.append(str(path))

    for name in MUTABLE_DIRS:
        path = data_dir / name
        if not path.exists():
            already_clean.append(str(path))
            continue
        for child in path.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
            removed.append(str(child))

    return {
        "data_dir": str(data_dir),
        "removed": removed,
        "already_clean": already_clean,
        "preserved": [
            str(data_dir / "raw"),
            "demo manifests and reviewed detector assets outside the mutable allowlist",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reset KaushalWatch mutable demo state without touching raw/reviewed assets."
    )
    parser.add_argument(
        "--data-dir",
        default=str(DEFAULT_DATA),
        help="Runtime data directory. Defaults to the repository data/ folder.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Perform the reset. Without --yes, print the planned allowlist only.",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir).expanduser().resolve()
    if not args.yes:
        print(json.dumps({
            "dry_run": True,
            "data_dir": str(data_dir),
            "files": [str(data_dir / name) for name in MUTABLE_FILES],
            "directories_to_clear": [str(data_dir / name) for name in MUTABLE_DIRS],
            "preserves_raw": True,
        }, indent=2))
        return

    payload = reset_demo_state(data_dir)
    payload["dry_run"] = False
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
