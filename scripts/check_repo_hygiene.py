from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

BLOCKED_SUFFIXES = {
    ".avi", ".mp4", ".mov", ".mkv", ".webm",
    ".pt", ".pth", ".onnx", ".bin",
}
BLOCKED_PREFIXES = (
    "data/raw/",
    "data/videos/",
    "data/evidence/",
    "data/edge/",
    "data/generated/",
    "data/annotations/",
    "evaluation/output/",
    "artifacts/",
)
MODEL_BINARY_PREFIX = "models/"
DEFAULT_MAX_BYTES = 5 * 1024 * 1024


def tracked_files(root: Path) -> list[Path]:
    output = subprocess.check_output(
        ["git", "ls-files", "-z"],
        cwd=root,
    )
    return [
        root / value.decode("utf-8")
        for value in output.split(b"\0")
        if value
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Reject generated/binary assets from the KaushalWatch git history.")
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    failures: list[str] = []

    for path in tracked_files(root):
        rel = path.relative_to(root).as_posix()
        suffix = path.suffix.lower()

        if any(rel.startswith(prefix) for prefix in BLOCKED_PREFIXES):
            failures.append(f"runtime/generated path is tracked: {rel}")
            continue

        if suffix in BLOCKED_SUFFIXES:
            failures.append(f"binary/video/model asset is tracked: {rel}")
            continue

        if rel.startswith(MODEL_BINARY_PREFIX) and suffix == ".xml":
            failures.append(f"OpenVINO model graph is tracked instead of downloaded at runtime: {rel}")
            continue

        if path.exists() and path.is_file() and path.stat().st_size > args.max_bytes:
            failures.append(
                f"tracked file exceeds {args.max_bytes} bytes: {rel} ({path.stat().st_size} bytes)"
            )

    if failures:
        print("Repository hygiene check FAILED:")
        for failure in failures:
            print(f"- {failure}")
        raise SystemExit(1)

    print("Repository hygiene check passed: no tracked video/model/runtime artifacts or oversized files.")


if __name__ == "__main__":
    main()
