"""Restricted, synthetic-only SIH demo state snapshot and isolated restoration.

Not a pilot database backup tool. It refuses unlabelled/real centre evidence,
symlinks, video, unexpected paths and existing restoration destinations.
Recovered evidence frame paths are rebased to the isolated destination.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
STATE_FILES = (
    "cases.json", "analysis_history.json", "centre_settings.json",
    "evidence_index.json", "edge_events.json", "edge/queue.json",
    "edge/schedule-state.json",
)
MAX_FILE = 25 * 1024 * 1024
MAX_TOTAL = 100 * 1024 * 1024
MAX_FILES = 300
MARKER = "_kaushalwatch_recovery_manifest.json"


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_file(name: str) -> bool:
    p = PurePosixPath(name)
    return (
        not p.is_absolute() and ".." not in p.parts
        and (name in STATE_FILES or (
            len(p.parts) == 2 and p.parts[0] == "evidence"
            and p.suffix.lower() in {".jpg", ".jpeg", ".png"}
        ))
    )


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_synthetic(root: Path, archive_files: dict[str, bytes]) -> None:
    if not archive_files.get("cases.json") or not archive_files.get("analysis_history.json"):
        raise ValueError("A restorable demo requires cases.json and analysis_history.json")
    cases = json.loads(archive_files["cases.json"])
    history = json.loads(archive_files["analysis_history.json"])
    if (not isinstance(cases, list) or not cases
            or not all(isinstance(r, dict) and r.get("details", {}).get("simulated") is True for r in cases)):
        raise ValueError("Recovery is restricted to fully simulated demo cases")
    if (not isinstance(history, list) or not history
            or not all(isinstance(r, dict) and r.get("details", {}).get("simulated") is True for r in history)):
        raise ValueError("Recovery is restricted to fully simulated analysis history")
    index = json.loads(archive_files.get("evidence_index.json", b"[]"))
    if not isinstance(index, list) or not all(
        isinstance(r, dict) and r.get("metadata", {}).get("simulated") is True
        for r in index
    ):
        raise ValueError("Recovery is restricted to simulated evidence index entries")

    allowed_images = set(archive_files)
    def assert_reference(record):
        if not isinstance(record, dict):
            raise ValueError("Malformed demo evidence record")
        name = record.get("frame_path")
        if not isinstance(name, str):
            raise ValueError("Missing stored evidence source path")
        actual = Path(name).expanduser().resolve()
        try:
            relative = actual.relative_to(root).as_posix()
        except ValueError as exc:
            raise ValueError("Evidence path escapes the synthetic demo root") from exc
        if not relative.startswith("evidence/") or relative not in allowed_images:
            raise ValueError("Evidence reference missing from the demo snapshot")
        if _digest(archive_files[relative]) != record.get("sha256"):
            raise ValueError("Evidence SHA does not match its demo record")
    for row in index:
        assert_reference(row)
    for row in cases:
        for entry in row.get("evidence", []):
            assert_reference(entry)


def snapshot_demo(data_root: Path, archive_path: Path) -> dict:
    root = Path(data_root).expanduser().resolve()
    archive = Path(archive_path).expanduser().resolve()
    if not root.is_dir() or archive.is_relative_to(root):
        raise ValueError("Source must exist and the snapshot must be outside its data directory")
    paths = [root / name for name in STATE_FILES if (root / name).exists()]
    evidence_dir = root / "evidence"
    if evidence_dir.exists():
        if evidence_dir.is_symlink():
            raise ValueError("Evidence directory symlinks are forbidden")
        paths.extend(path for path in evidence_dir.rglob("*") if path.is_file() or path.is_symlink())
    content: dict[str, bytes] = {}
    total = 0
    for path in paths:
        if path.is_symlink():
            raise ValueError("Demo snapshot refuses symlink entries")
        relative = path.relative_to(root).as_posix()
        if not _safe_file(relative) or not path.is_file():
            raise ValueError(f"Unexpected or unsafe demo snapshot file: {relative}")
        size = path.stat().st_size
        if size > MAX_FILE:
            raise ValueError("Demo snapshot file exceeds the per-file limit")
        total += size
        if total > MAX_TOTAL or len(content) >= MAX_FILES:
            raise ValueError("Demo snapshot exceeds size or file-count limits")
        content[relative] = path.read_bytes()
    _assert_synthetic(root, content)
    index = {
        "schema_version": 1, "scope": "synthetic_demo_only",
        "source_root": str(root),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": {name: {"sha256": _digest(data), "bytes": len(data)}
                  for name, data in sorted(content.items())},
        "claim_boundary": "No raw videos; not a real-centre, encrypted or transactional backup.",
    }
    archive.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(dir=archive.parent, prefix=".demo-recovery-",
                                         suffix=".zip", delete=False) as handle:
            tmp_path = Path(handle.name)
        with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as z:
            for name, data in sorted(content.items()):
                z.writestr(name, data)
            z.writestr(MARKER, json.dumps(index, indent=2).encode("utf-8"))
        os.replace(tmp_path, archive)
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
    return {"archive": str(archive), "file_count": len(content),
            "bytes": total, "archive_sha256": _digest(archive.read_bytes()),
            "scope": "synthetic_demo_only"}


def restore_demo(archive_path: Path, destination: Path) -> dict:
    archive = Path(archive_path).expanduser().resolve()
    target = Path(destination).expanduser().resolve()
    if target.exists() or target == Path(target.anchor):
        raise ValueError("Restore requires a NEW destination directory; refusing overwrite")
    if target.is_relative_to(archive.parent / archive.name):
        raise ValueError("Destination must not be inside the archive path")
    with zipfile.ZipFile(archive, "r") as z:
        names = z.namelist()
        if len(names) != len(set(names)) or names.count(MARKER) != 1:
            raise ValueError("Ambiguous recovery archive members")
        metadata = json.loads(z.read(MARKER))
        if metadata.get("schema_version") != 1 or metadata.get("scope") != "synthetic_demo_only":
            raise ValueError("Recovery bundle is not an approved synthetic demo snapshot")
        expected = metadata.get("files")
        if not isinstance(expected, dict) or set(names) != set(expected) | {MARKER}:
            raise ValueError("Recovery archive files disagree with its manifest")
        total = 0
        restored: dict[str, bytes] = {}
        for member in z.infolist():
            if member.filename == MARKER:
                continue
            if not _safe_file(member.filename) or member.is_dir() or member.file_size > MAX_FILE:
                raise ValueError("Unsafe demo recovery archive member")
            total += member.file_size
            if total > MAX_TOTAL or len(restored) >= MAX_FILES:
                raise ValueError("Recovery archive exceeds safe bounds")
            data = z.read(member)
            if _digest(data) != expected[member.filename].get("sha256") or len(data) != expected[member.filename].get("bytes"):
                raise ValueError("Recovery archive content SHA or size mismatch")
            restored[member.filename] = data
    source_root = Path(metadata["source_root"]).expanduser().resolve()
    _assert_synthetic(source_root, restored)
    target.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".kaushalwatch-restoring-", dir=target.parent))
    try:
        for name, data in restored.items():
            output = stage / name
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(data)

        # Frame paths in the JSON demo ledgers are absolute by design.
        # Rebase only verified paths under the original evidence directory.
        for name in ("cases.json", "evidence_index.json"):
            path = stage / name
            if not path.exists():
                continue
            rows = _read_json(path)
            records = rows if name == "evidence_index.json" else [
                ev for case in rows for ev in case.get("evidence", [])
            ]
            for record in records:
                old = Path(record["frame_path"]).resolve()
                relative = old.relative_to(source_root)
                record["frame_path"] = str(stage / relative)
            path.write_text(json.dumps(rows, indent=2), encoding="utf-8")

        # Rename the staged root atomically into the new destination,
        # using the final directory paths for evidence records.
        for name in ("cases.json", "evidence_index.json"):
            path = stage / name
            if not path.exists():
                continue
            rows = _read_json(path)
            records = rows if name == "evidence_index.json" else [
                ev for case in rows for ev in case.get("evidence", [])
            ]
            for record in records:
                relative = Path(record["frame_path"]).relative_to(stage)
                record["frame_path"] = str(target / relative)
            path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
        os.replace(stage, target)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return {"restored_to": str(target), "file_count": len(restored),
            "source_integrity_verified": True, "scope": "synthetic_demo_only",
            "existing_data_overwritten": False}


def main() -> None:
    parser = argparse.ArgumentParser(description="Isolated synthetic demo state backup/restore")
    sub = parser.add_subparsers(dest="command", required=True)
    backup = sub.add_parser("snapshot")
    backup.add_argument("--data-root", required=True)
    backup.add_argument("--archive", required=True)
    backup.add_argument("--yes", action="store_true")
    recover = sub.add_parser("restore")
    recover.add_argument("--archive", required=True)
    recover.add_argument("--destination", required=True)
    recover.add_argument("--yes", action="store_true")
    args = parser.parse_args()
    if not args.yes:
        print(json.dumps({"dry_run": True, "requested_command": args.command,
                          "note": "Specify --yes to write a synthetic-only recovery bundle or restore into a NEW destination."}, indent=2))
        return
    result = (snapshot_demo(Path(args.data_root), Path(args.archive))
              if args.command == "snapshot"
              else restore_demo(Path(args.archive), Path(args.destination)))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
