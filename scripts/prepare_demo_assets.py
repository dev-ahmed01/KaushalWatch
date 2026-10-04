from __future__ import annotations

import argparse
import shutil
from pathlib import Path


ALIASES = {
    "attendance_clean": "demo-attendance-clean.mp4",
    "attendance_mismatch": "demo-attendance-mismatch.mp4",
    "practical_authorized": "demo-practical-authorized.mp4",
    "practical_unauthorized": "demo-practical-unauthorized.mp4",
    "equipment_discrepancy": "demo-equipment-discrepancy.mp4",
    "camera_tamper": "demo-camera-tamper.mp4",
    "duplicate_evidence": "demo-duplicate-evidence.mp4",
}


def copy_asset(source: str | None, destination_dir: Path, alias: str) -> None:
    if not source:
        return

    src = Path(source).expanduser().resolve()
    if not src.exists():
        raise SystemExit(f"Source for {alias} does not exist: {src}")

    suffix = src.suffix.lower()
    target_name = ALIASES[alias]
    if suffix and suffix != ".mp4":
        target_name = Path(target_name).with_suffix(suffix).name

    destination_dir.mkdir(parents=True, exist_ok=True)
    target = destination_dir / target_name
    shutil.copy2(src, target)
    print(f"{alias}: {src.name} -> {target}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Copy selected local demo clips into presenter-friendly aliases without "
            "renaming the original research/dataset files."
        )
    )
    parser.add_argument("--out-dir", default="demo_assets")
    parser.add_argument("--attendance-clean")
    parser.add_argument("--attendance-mismatch")
    parser.add_argument("--practical-authorized")
    parser.add_argument("--practical-unauthorized")
    parser.add_argument("--equipment-discrepancy")
    parser.add_argument("--camera-tamper")
    parser.add_argument("--duplicate-evidence")
    args = parser.parse_args()

    destination = Path(args.out_dir).expanduser().resolve()

    for alias in ALIASES:
        copy_asset(getattr(args, alias), destination, alias)

    print(
        "\nOriginal files were left untouched. Use the descriptive copies from "
        f"{destination} during the judge walkthrough."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
