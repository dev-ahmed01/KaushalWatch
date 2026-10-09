"""Release recovery smoke: synthetic-only snapshots, no production data."""
from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from app.models import CaseStatus
from app.services.case_store import CaseStore
from app.services.offline_queue import EdgeEventQueue
from scripts.demo_recovery import snapshot_demo, restore_demo
from scripts.prepare_demo_state import prepare_demo_state


def _prepared_state(tmp_path):
    original = tmp_path / "isolated-synthetic-demo"
    prepare_demo_state(original)
    case_store = CaseStore(original / "cases.json")
    case_store.apply_review_action(
        "SIM-KA-104-ATT", CaseStatus.confirmed,
        note="Synthetic evidence confirmed for recovery rehearsal.",
        actor="synthetic-operator-01",
    )
    queue = EdgeEventQueue(original / "edge" / "queue.json")
    event = queue.enqueue("analysis_summary", {
        "centre_id": "DEMO-KA-104", "simulated": True, "raw_video_uploaded": False,
    })
    (original / "raw").mkdir(exist_ok=True)
    (original / "raw" / "do-not-back-up.mp4").write_bytes(b"NO_REAL_VIDEO")
    return original, event


def test_demo_recovery_preserves_review_audit_evidence_and_offline_queue(tmp_path):
    source, queued = _prepared_state(tmp_path)
    bundle = tmp_path / "synthetic-demo-recovery.zip"
    snapshot = snapshot_demo(source, bundle)
    assert snapshot["scope"] == "synthetic_demo_only"
    with zipfile.ZipFile(bundle) as z:
        paths = set(z.namelist())
    assert "raw/do-not-back-up.mp4" not in paths
    assert "edge/queue.json" in paths
    assert "cases.json" in paths

    destination = tmp_path / "recovered-synthetic-demo"
    result = restore_demo(bundle, destination)
    assert result["source_integrity_verified"] is True
    assert result["existing_data_overwritten"] is False
    restored_case = CaseStore(destination / "cases.json").get("SIM-KA-104-ATT")
    assert restored_case.status == CaseStatus.confirmed
    assert len(restored_case.review_history) == 2
    assert restored_case.review_history[-1]["actor"] == "synthetic-operator-01"
    assert len(EdgeEventQueue(destination / "edge" / "queue.json").pending()) == 1
    assert EdgeEventQueue(destination / "edge" / "queue.json").pending()[0]["event_id"] == queued["event_id"]

    evidence = restored_case.evidence[0]
    evidence_path = Path(evidence.frame_path)
    assert evidence_path.is_file()
    assert evidence_path.is_relative_to(destination)
    from app.services.evidence import sha256_file
    assert sha256_file(evidence_path) == evidence.sha256
    assert not (destination / "raw" / "do-not-back-up.mp4").exists()

    with pytest.raises(ValueError, match="NEW destination"):
        restore_demo(bundle, destination)


def test_recovery_rejects_modified_archived_ledger_before_creating_files(tmp_path):
    source, _ = _prepared_state(tmp_path)
    archive = tmp_path / "original.zip"
    snapshot_demo(source, archive)
    broken = tmp_path / "tampered.zip"
    with zipfile.ZipFile(archive) as incoming, zipfile.ZipFile(broken, "w") as outgoing:
        for name in incoming.namelist():
            content = incoming.read(name)
            if name == "cases.json":
                content += b"\n "
            outgoing.writestr(name, content)
    target = tmp_path / "must-not-restore"
    with pytest.raises(ValueError, match="SHA or size mismatch"):
        restore_demo(broken, target)
    assert not target.exists()


def test_recovery_rejects_zip_traversal_and_external_unlisted_files(tmp_path):
    source, _ = _prepared_state(tmp_path)
    archive = tmp_path / "original.zip"
    snapshot_demo(source, archive)
    tampered = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive) as incoming, zipfile.ZipFile(tampered, "w") as outgoing:
        for name in incoming.namelist():
            outgoing.writestr(name, incoming.read(name))
        outgoing.writestr("../injected-secret.txt", "NO")
    with pytest.raises(ValueError, match="archive files disagree"):
        restore_demo(tampered, tmp_path / "refused")


def test_snapshot_refuses_non_simulated_cases_and_leaves_archive_absent(tmp_path):
    source, _ = _prepared_state(tmp_path)
    cases = json.loads((source / "cases.json").read_text())
    cases[0]["details"]["simulated"] = False
    (source / "cases.json").write_text(json.dumps(cases))
    bundle = tmp_path / "reject-real-centre-state.zip"
    with pytest.raises(ValueError, match="fully simulated demo cases"):
        snapshot_demo(source, bundle)
    assert not bundle.exists()


def test_snapshot_refuses_evidence_external_path_and_symlink(tmp_path):
    source, _ = _prepared_state(tmp_path)
    cases = json.loads((source / "cases.json").read_text())
    cases[0]["evidence"][0]["frame_path"] = str(tmp_path / "external-photo.jpg")
    (source / "cases.json").write_text(json.dumps(cases))
    with pytest.raises(ValueError, match="escapes"):
        snapshot_demo(source, tmp_path / "reject-external.zip")
