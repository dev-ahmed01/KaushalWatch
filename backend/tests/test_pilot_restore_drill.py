"""The CI-only restore drill cannot touch a remote or protected database."""
from __future__ import annotations

import os
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))
from scripts import drill_postgres_restore as drill
from app.services.dependency_readiness import REQUIRED_TABLES


def _good(monkeypatch):
    monkeypatch.setenv("KAUSHALWATCH_TEST_DATABASE", "isolated_ci")
    monkeypatch.setenv("KAUSHALWATCH_DATABASE_URL",
                       "postgresql://ci:CI-SECRET@127.0.0.1:5432/kaushalwatch_ci")
    for name in ("KAUSHALWATCH_ENV", "PGHOSTADDR", "PGSERVICE", "PGSERVICEFILE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(drill.shutil, "which", lambda name: "/usr/bin/" + name)


def test_restore_snapshot_schema_tracks_full_v3_runtime():
    assert set(drill.TABLES) == set(REQUIRED_TABLES) | {"kw_schema_migrations"}
    assert len(drill.TABLES) == 11
    for name in (
        "kw_camera_registry", "kw_camera_references", "kw_camera_jobs",
        "kw_camera_observations", "kw_camera_audit",
    ):
        assert name in drill.TABLES


def test_explicit_local_disposable_connection_is_accepted(monkeypatch):
    _good(monkeypatch)
    env, dsn = drill._allowed()
    assert "127.0.0.1" in dsn
    assert env["PGHOST"] == "127.0.0.1"
    assert env["PGPORT"] == "5432"
    assert env["PGDATABASE"] if "PGDATABASE" in env else True


@pytest.mark.parametrize("override", [
    "postgresql://ci:CI-SECRET@db.example.org:5432/kaushalwatch_ci",
    "postgresql://ci:CI-SECRET@127.0.0.1:5432/production",
    "postgresql://ci:CI-SECRET@127.0.0.1:6432/kaushalwatch_ci",
    "postgresql://ci:CI-SECRET@127.0.0.1:5432/kaushalwatch_ci?hostaddr=203.0.113.33",
    "postgresql://ci:CI-SECRET@127.0.0.1:5432/kaushalwatch_ci?service=remote",
    "postgresql://ci:CI-SECRET@127.0.0.1:5432/kaushalwatch_ci?servicefile=/tmp/ci",
    "postgresql://ci:CI-SECRET@127.0.0.1:5432/kaushalwatch_ci?host=remote.example.org",
    "postgresql://ci:CI-SECRET@127.0.0.1:5432/kaushalwatch_ci?hostaddr=127.0.0.1",
    "postgresql://broken%ZZ@127.0.0.1:5432/kaushalwatch_ci",
])
def test_remote_and_service_redirects_denied_before_connect(monkeypatch, override):
    _good(monkeypatch)
    monkeypatch.setenv("KAUSHALWATCH_DATABASE_URL", override)
    with pytest.raises(RuntimeError) as err:
        drill._allowed()
    assert "CI-SECRET" not in str(err.value)


@pytest.mark.parametrize("key,value", [
    ("KAUSHALWATCH_TEST_DATABASE", ""),
    ("KAUSHALWATCH_ENV", "pilot"),
    ("KAUSHALWATCH_ENV", "production"),
    ("PGHOSTADDR", "203.0.113.33"),
    ("PGHOSTADDR", "127.0.0.1"),
    ("PGSERVICE", "ci-service"),
    ("PGSERVICEFILE", "/tmp/libpq-service"),
])
def test_production_and_ambient_destination_overrides_denied(monkeypatch, key, value):
    _good(monkeypatch)
    monkeypatch.setenv(key, value)
    with pytest.raises(RuntimeError):
        drill._allowed()


def test_refusal_occurs_before_any_database_connection(monkeypatch):
    _good(monkeypatch)
    monkeypatch.setenv("PGHOSTADDR", "203.0.113.33")
    calls = []
    monkeypatch.setattr(drill.psycopg, "connect",
                        lambda *a, **kw: calls.append(("connected", a, kw)))
    monkeypatch.setattr(drill.subprocess, "run",
                        lambda *a, **kw: calls.append(("subprocess", a, kw)))
    with pytest.raises(RuntimeError):
        drill.drill()
    assert calls == []
