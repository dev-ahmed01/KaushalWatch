"""Privacy-safe boundary for API JSON containing retained evidence records.

Internal EvidenceRecord.frame_path remains necessary for backend integrity,
offline recovery and persistence, but clients need only opaque evidence IDs
to request the protected /evidence/{id}.jpg endpoint.
"""
from __future__ import annotations

from typing import Any


def redact_local_evidence_paths(value: Any) -> Any:
    """Copy response payloads without revealing local evidence/video paths."""
    if isinstance(value, list):
        return [redact_local_evidence_paths(entry) for entry in value]
    if isinstance(value, tuple):
        return [redact_local_evidence_paths(entry) for entry in value]
    if isinstance(value, dict):
        return {
            key: redact_local_evidence_paths(item)
            for key, item in value.items()
            if key not in {"frame_path", "raw_video_path", "source_video_path",
                           "local_video_path", "local_frame_path"}
        }
    return value
