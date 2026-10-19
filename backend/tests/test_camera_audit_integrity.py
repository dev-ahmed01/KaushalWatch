"""Privacy-safe read-only audit chain validation: unit and CLI denial paths."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from app.services.camera_trust_store import _json_hash
from scripts.check_camera_audit_integrity import (
    _chain, _configured, evaluate, MAX_EVENTS, scan_database,
)
from scripts.check_pilot_rollout import evaluate as pilot_evaluate

CAM = "11111111-1111-4111-8111-111111111111"
CAM2 = "22222222-2222-4222-8222-222222222222"
DSN = "postgresql://operator:SHOULD-NOT-ECHO@db.example.invalid/kw?sslmode=verify-full&gssencmode=disable"
ENV = {
    "KAUSHALWATCH_ENV": "pilot",
    "KAUSHALWATCH_STORAGE_BACKEND": "postgres",
    "KAUSHALWATCH_DATABASE_URL": DSN,
}


def make_events(camera=CAM, count=2):
    previous = "0" * 64
    rows = []
    for sequence in range(1, count + 1):
        payload = {"source_pin_synthetic": "abc123", "step": sequence}
        body = {"camera_id": camera, "sequence": sequence,
                "actor": "CI-SYNTHETIC", "event": "analysis_reviewed",
                "payload": payload, "previous_sha256": previous}
        digest = _json_hash(body)
        rows.append({**body, "event_sha256": digest})
        previous = digest
    return rows


def test_large_complete_chain_over_ui_limit_is_accepted():
    rows = make_events(count=2002)
    outcome = _chain(iter(rows), 1)
    assert outcome["valid"] is True and outcome["events_checked"] == 2002


@pytest.mark.parametrize("mutation", [
    lambda r: r.__setitem__("sequence", 3),
    lambda r: r.__setitem__("previous_sha256", "f" * 64),
    lambda r: r.__setitem__("event_sha256", "f" * 64),
    lambda r: r.__setitem__("payload", {"tampered": True}),
    lambda r: r.__setitem__("actor", "forged"),
    lambda r: r.__setitem__("payload", []),
])
def test_every_tamper_breaks_audit(mutation):
    rows = make_events()
    mutation(rows[1])
    assert _chain(iter(rows), 1)["valid"] is False


def test_missing_camera_and_empty_records_fail_closed():
    assert not _chain(iter(make_events()), 2)["valid"]
    assert not _chain(iter([]), 0)["valid"]
    assert not _chain(iter([]), 1)["valid"]
    mixed = make_events(CAM) + make_events(CAM2)
    assert _chain(iter(mixed), 2)["valid"]
    assert not _chain(iter(mixed + make_events(CAM)), 2)["valid"]


def test_bounded_audit_never_claims_truncated_success(monkeypatch):
    import scripts.check_camera_audit_integrity as script
    monkeypatch.setattr(script, "MAX_EVENTS", 2)
    assert script._chain(iter(make_events(count=3)), 1)["valid"] is False


def test_protected_verified_tls_required_and_no_network_when_missing():
    bad = {**ENV, "KAUSHALWATCH_DATABASE_URL": "postgresql://db.invalid/kw"}
    assert _configured(ENV) is True
    assert _configured(bad) is False
    assert _configured({**ENV, "KAUSHALWATCH_ENV": "development"}) is False
    called = []
    result = evaluate(bad, probe=True,
                      connection_factory=lambda *a, **kw: called.append(a))
    assert result["read_only_database_audit"] == "BLOCKED"
    assert not called
    assert "SHOULD-NOT-ECHO" not in json.dumps(result)
    result = evaluate(ENV, probe=False)
    assert result["checks"]["full_audit_chain_valid"] == "NOT_PROBED"


class Cursor:
    def __init__(self, data): self.data = data
    def fetchone(self): return self.data
    def fetchall(self): return self.data


class StubDB:
    def __init__(self, *, good=True, trigger=True, events=None):
        self.good = good
        self.trigger = trigger
        self.events = events if events is not None else make_events()
        self.queries = []
    def execute(self, query, params=None):
        sql = " ".join(query.split())
        self.queries.append(sql)
        if sql == "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY":
            return Cursor(None)
        if "FROM kw_camera_registry" in sql and "COUNT(" in sql:
            return Cursor({"count": 1})
        if "FROM kw_camera_registry r" in sql:
            return Cursor({"missing": False if self.good else True})
        if "FROM pg_trigger" in sql:
            if not self.trigger: return Cursor(None)
            return Cursor({
                "enabled": "O",
                "definition": (
                    "CREATE TRIGGER kw_camera_audit_no_update BEFORE DELETE OR "
                    "UPDATE ON public.kw_camera_audit FOR EACH ROW EXECUTE FUNCTION "
                    "kw_camera_audit_immutable()"
                ),
                "function_definition": (
                    "CREATE FUNCTION kw_camera_audit_immutable() RETURNS trigger "
                    "AS $$ BEGIN RAISE EXCEPTION "
                    "'Camera Trust audit events are immutable'; END $$ LANGUAGE plpgsql"
                ),
            })
        if "FROM kw_camera_audit" in sql:
            if params and len(params) == 3:
                camera, seq, _ = params
                return Cursor([r for r in self.events
                               if (r["camera_id"], r["sequence"]) >
                                  (str(camera), seq)])
            return Cursor(self.events)
        raise AssertionError("Unexpected read-only audit SQL")


def test_scan_reports_success_only_for_complete_triggered_history():
    good = StubDB()
    checks = scan_database(good)
    assert all(checks.values())
    assert good.queries
    assert all(("SELECT" in q or "pg_get_functiondef" in q) for q in good.queries)
    assert scan_database(StubDB(trigger=False))["immutable_trigger_enabled"] is False
    assert scan_database(StubDB(good=False))["no_cameras_missing_audit"] is False


class Session:
    def __init__(self, db): self.db = db
    def __enter__(self): return self.db
    def __exit__(self, *a): return False


def test_privileged_probe_is_read_only_and_never_leaks_database_metadata():
    db = StubDB()
    calls = []
    def connect(*args, **kwargs):
        calls.append((args, kwargs))
        return Session(db)
    report = evaluate(ENV, probe=True, connection_factory=connect)
    assert report["read_only_database_audit"] == "CHECKS_PASS"
    assert report["database_snapshot_attempted"] is True
    assert db.queries[0].startswith("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
    assert report["pilot_activation"] == "BLOCKED_PENDING_EXTERNAL_AUTHORIZATION"
    assert report["database_admin_resigning_the_chain_excluded"] is False
    assert "SHOULD-NOT-ECHO" not in json.dumps(report)
    assert CAM not in json.dumps(report) and "abc123" not in json.dumps(report)
    assert len(calls) == 1


def test_db_exception_and_missing_trigger_block_without_leakage():
    def explode(*args, **kwargs):
        raise RuntimeError("SECRET PASSWORD DB HOST SHOULD NOT ECHO")
    blocked = evaluate(ENV, probe=True, connection_factory=explode)
    assert blocked["read_only_database_audit"] == "BLOCKED"
    assert "SECRET PASSWORD" not in json.dumps(blocked)
    blocked = evaluate(ENV, probe=True,
                       connection_factory=lambda *a, **kw: Session(StubDB(trigger=False)))
    assert blocked["read_only_database_audit"] == "BLOCKED"


def test_pilot_gate_not_probed_cannot_claim_eligibility(monkeypatch):
    assert pilot_evaluate({})["checks"]["camera_audit_chain_integrity"] == "NOT_PROBED"
    import scripts.check_pilot_rollout as rollout
    monkeypatch.setattr(rollout, "inspect_camera_audit", lambda *a, **kw: {
        "read_only_database_audit": "BLOCKED", "database_snapshot_attempted": True,
    })
    denied = rollout.evaluate({}, probe_camera_audit=True)
    assert denied["checks"]["camera_audit_chain_integrity"] == "BLOCKED"
    assert denied["eligible_to_request_external_pilot_signoff"] is False


def test_offline_cli_reports_only_blocked_status():
    completed = subprocess.run([
        sys.executable, str(ROOT / "scripts/check_camera_audit_integrity.py"),
        "--status",
    ], capture_output=True, text=True, cwd=ROOT, timeout=15)
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["read_only_database_audit"] == "BLOCKED"
    assert result["database_snapshot_attempted"] is False
