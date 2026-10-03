from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import cv2
import numpy as np
from app.models import EvidenceRecord


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def dhash(frame: np.ndarray) -> str:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
    small = cv2.resize(gray, (9, 8))
    diff = small[:, 1:] > small[:, :-1]
    bits = "".join("1" if x else "0" for x in diff.flatten())
    return f"{int(bits, 2):016x}"


def hamming_hex(a: str, b: str) -> int:
    return (int(a, 16) ^ int(b, 16)).bit_count()


def find_duplicate(phash: str, index_path: Path, max_distance: int = 4) -> str | None:
    if not index_path.exists():
        return None
    rows = json.loads(index_path.read_text())
    for row in rows:
        if hamming_hex(phash, row["perceptual_hash"]) <= max_distance:
            return row["evidence_id"]
    return None


def persist_evidence(frame: np.ndarray, evidence_dir: Path, index_path: Path, evidence_id: str, metadata: dict) -> EvidenceRecord:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    path = evidence_dir / f"{evidence_id}.jpg"
    if not cv2.imwrite(str(path), frame):
        raise RuntimeError("Could not persist evidence frame")
    p_hash = dhash(frame)
    duplicate_of = find_duplicate(p_hash, index_path)
    record = EvidenceRecord(
        evidence_id=evidence_id,
        created_at=datetime.now(timezone.utc).isoformat(),
        frame_path=str(path),
        sha256=sha256_file(path),
        perceptual_hash=p_hash,
        duplicate_of=duplicate_of,
        metadata=metadata,
    )
    rows = json.loads(index_path.read_text()) if index_path.exists() else []
    rows.append(record.model_dump())
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(rows, indent=2))
    return record
