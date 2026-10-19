"""Pilot deployment health never accepts v2, missing v3 tables, or a wrong DSN.

All tests use pure synthetic DB connections. No real cloud calls or field footage.
"""
from __future__ import annotations

from contextlib import contextmanager
import sys
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"backend"))

from app.services.dependency_readiness import dependencies_ready, REQUIRED_TABLES
from scripts.check_camera_trust_deployment import check_environment


class Rows:
    def __init__(self, data):self.data=data
    def fetchall(self):return self.data
    def fetchone(self):return self.data

class Database:
    def __init__(self, versions, missing=()):
        self.versions=versions
        self.missing=set(missing)
        self.probed=[]
    def execute(self, sql, params=None):
        normalized=" ".join(sql.split()).lower()
        assert normalized.startswith("select "), normalized
        self.probed.append((normalized, params))
        if "from kw_schema_migrations" in normalized:
            return Rows([{"version":n} for n in self.versions])
        if "to_regclass(" in normalized:
            assert params and len(params)==1
            name=params[0]
            return Rows({"name":None if name in self.missing else name})
        raise AssertionError("Unexpected database query")


def configure_protected(monkeypatch, database):
    monkeypatch.setenv("KAUSHALWATCH_ENV","pilot")
    monkeypatch.setenv("KAUSHALWATCH_STORAGE_BACKEND","postgres")
    monkeypatch.setenv("KAUSHALWATCH_EVIDENCE_BACKEND","s3")
    monkeypatch.setenv("KAUSHALWATCH_REVIEW_AUTH_MODE","oidc")
    from app.services import officer_permissions,object_evidence,review_access,postgres_store
    monkeypatch.setattr(officer_permissions,"configured_principals",lambda:{"reviewer":"allowed"})
    monkeypatch.setattr(object_evidence,"configuration",lambda:{"validated":"configuration-only"})
    monkeypatch.setattr(review_access,"_configuration",lambda:("oidc",{}))
    @contextmanager
    def connection():
        yield database
    monkeypatch.setattr(postgres_store,"connection",connection)


@pytest.mark.parametrize(("versions","missing","ready"),[
    ({1,2}, (), False),
    ({1,3}, (), False),
    ({1,2,3}, ("kw_camera_observations",), False),
    ({1,2,3}, ("kw_camera_references",), False),
    ({1,2,3}, (), True),
])
def test_pilot_readiness_requires_schema_v3_and_all_tables(monkeypatch,versions,missing,ready):
    db=Database(versions,missing)
    configure_protected(monkeypatch,db)
    assert dependencies_ready() is ready
    import app.main as main
    response=TestClient(main.app).get("/api/ready")
    assert response.status_code==(200 if ready else 503)
    assert response.json()=={"ready":ready}
    assert response.headers["cache-control"]=="no-store"
    assert "select" in db.probed[0][0]


def test_local_demo_readiness_remains_compatible(monkeypatch):
    monkeypatch.setenv("KAUSHALWATCH_ENV","development")
    assert dependencies_ready() is True


def test_preflight_probes_only_explicit_candidate_dsn(monkeypatch):
    import psycopg
    candidate="postgresql://candidate:FAKE-DO-NOT-ECHO@example.invalid/pilot"
    ambient="postgresql://unrelated:NEVER_USE@example.invalid/other"
    monkeypatch.setenv("KAUSHALWATCH_DATABASE_URL",ambient)
    requested=[]
    database=Database({1,2,3})
    @contextmanager
    def fake_connect(dsn, **options):
        requested.append((dsn,options))
        yield database
    monkeypatch.setattr(psycopg,"connect",fake_connect)
    env={
      "KAUSHALWATCH_ENV":"pilot","KAUSHALWATCH_STORAGE_BACKEND":"postgres",
      "KAUSHALWATCH_DATABASE_URL":candidate,
    }
    report=check_environment("web",env,probe_db=True)
    assert report["checks"]["postgres_camera_schema_v3"]=="PASS"
    assert requested and all(dsn==candidate for dsn,_ in requested)
    assert all(options["connect_timeout"]==5 for _,options in requested)
    assert ambient not in str(report) and candidate not in str(report)
    assert "FAKE-DO-NOT-ECHO" not in str(report)
    assert len([sql for sql,_ in database.probed if "to_regclass" in sql])==len(REQUIRED_TABLES)


@pytest.mark.parametrize(("versions","missing"),[
    ({1,2},()),({1,2,3},("kw_camera_jobs",)),({1,2,3},("kw_evidence_objects",))
])
def test_candidate_database_with_incomplete_migration_stays_blocked(
    monkeypatch, versions,missing
):
    import psycopg
    @contextmanager
    def fake_connect(dsn,**opts):
        yield Database(versions,missing)
    monkeypatch.setattr(psycopg,"connect",fake_connect)
    env={"KAUSHALWATCH_ENV":"pilot","KAUSHALWATCH_STORAGE_BACKEND":"postgres",
         "KAUSHALWATCH_DATABASE_URL":"postgresql://candidate.invalid/test"}
    result=check_environment("web",env,probe_db=True)
    assert result["checks"]["postgres_camera_schema_v3"]=="BLOCKED"


def test_missing_postgres_driver_or_connection_error_fails_closed(monkeypatch):
    import psycopg
    def unavailable(*a,**kw):raise RuntimeError("fake secret that must not be emitted")
    monkeypatch.setattr(psycopg,"connect",unavailable)
    data=check_environment("web",{
       "KAUSHALWATCH_ENV":"pilot","KAUSHALWATCH_STORAGE_BACKEND":"postgres",
       "KAUSHALWATCH_DATABASE_URL":"postgresql://bad:test@nowhere.invalid/db",
    },probe_db=True)
    assert data["checks"]["postgres_camera_schema_v3"]=="BLOCKED"
    assert "fake secret" not in str(data)
