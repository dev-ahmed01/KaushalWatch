"""PostgreSQL persistence for protected KaushalWatch API instances.

An explicit schema migration is required. No implicit JSON import or database
creation is performed. Operations are transactional, with a shared transaction
for edge receipts, derived cases and analysis history.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
import os
from typing import Iterator

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.models import CaseStatus, ComplianceCase
from app.services.case_store import ALLOWED_CASE_TRANSITIONS
from app.services.centre_settings import DEFAULT_SETTINGS


_ACTIVE: ContextVar[psycopg.Connection | None] = ContextVar("kw_pg_tx", default=None)


def _dsn() -> str:
    dsn = os.environ.get("KAUSHALWATCH_DATABASE_URL", "")
    if not dsn:
        raise RuntimeError("PostgreSQL selected but KAUSHALWATCH_DATABASE_URL is missing")
    if not dsn.startswith(("postgresql://", "postgres://")):
        raise RuntimeError("A PostgreSQL DSN is required")
    return dsn


@contextmanager
def connection() -> Iterator[psycopg.Connection]:
    existing = _ACTIVE.get()
    if existing is not None:
        yield existing
        return
    # A new transaction and connection per operation ensures separate API
    # processes observe committed records; never reuse a global connection.
    with psycopg.connect(_dsn(), row_factory=dict_row, connect_timeout=5) as db:
        yield db


@contextmanager
def unit_of_work(*, edge: bool = False) -> Iterator[None]:
    if _ACTIVE.get() is not None:
        raise RuntimeError("Nested PostgreSQL write transaction is not supported")
    with psycopg.connect(_dsn(), row_factory=dict_row, connect_timeout=5) as db:
        token = _ACTIVE.set(db)
        try:
            if edge:
                # All edge sync receipts and derived writes share one globally
                # serialized transaction. Replaying a receipt across workers
                # cannot duplicate a case or history row.
                db.execute("SELECT pg_advisory_xact_lock(%s)", (82630091,))
            yield
        finally:
            _ACTIVE.reset(token)
        # Connection context commits on success, rolls back on exception.


def _case_from_row(row: dict | None) -> ComplianceCase | None:
    return ComplianceCase.model_validate(row["payload"]) if row else None


def _apply_action(
    case: ComplianceCase, status: CaseStatus, note: str | None, actor: str,
    *, auto_open: bool,
) -> ComplianceCase:
    final = {CaseStatus.confirmed, CaseStatus.false_positive, CaseStatus.resolved}
    if auto_open and status in final and (not note or not note.strip()):
        raise ValueError("Final case decisions require an officer review note")
    if auto_open and case.status == CaseStatus.open and status in final:
        case.review_history.extend([
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "actor": actor, "from_status": CaseStatus.open.value,
                "to_status": CaseStatus.under_review.value,
                "note": "Officer opened the evidence review.",
            },
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "actor": actor, "from_status": CaseStatus.under_review.value,
                "to_status": status.value,
                "note": note.strip(),
            },
        ])
        case.status = status
        return case
    previous = case.status
    if status == previous:
        return case
    if status not in ALLOWED_CASE_TRANSITIONS.get(previous, set()):
        raise ValueError(f"Invalid case transition: {previous.value} -> {status.value}")
    case.status = status
    case.review_history.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actor": actor, "from_status": previous.value, "to_status": status.value,
        "note": note,
    })
    return case


class PostgresCaseStore:
    def list(self) -> list[ComplianceCase]:
        with connection() as db:
            rows = db.execute("SELECT payload FROM kw_cases ORDER BY created_order").fetchall()
        return [ComplianceCase.model_validate(row["payload"]) for row in rows]

    def get(self, case_id: str) -> ComplianceCase | None:
        with connection() as db:
            row = db.execute("SELECT payload FROM kw_cases WHERE case_id = %s", (case_id,)).fetchone()
        return _case_from_row(row)

    def save(self, case: ComplianceCase) -> ComplianceCase:
        payload = Jsonb(case.model_dump(mode="json"))
        with connection() as db:
            db.execute(
                """INSERT INTO kw_cases(case_id, centre_id, payload)
                   VALUES (%s, %s, %s)
                   ON CONFLICT(case_id) DO UPDATE
                     SET payload = EXCLUDED.payload,
                         centre_id = EXCLUDED.centre_id,
                         updated_at = CURRENT_TIMESTAMP""",
                (case.case_id, case.centre_id, payload),
            )
        return case

    def save_if_absent(self, case: ComplianceCase) -> bool:
        with connection() as db:
            row = db.execute(
                """INSERT INTO kw_cases(case_id, centre_id, payload)
                   VALUES (%s, %s, %s) ON CONFLICT(case_id) DO NOTHING
                   RETURNING case_id""",
                (case.case_id, case.centre_id, Jsonb(case.model_dump(mode="json"))),
            ).fetchone()
        return row is not None

    def _transition(self, case_id: str, status: CaseStatus, note: str | None,
                    actor: str, *, auto_open: bool) -> ComplianceCase | None:
        with connection() as db:
            row = db.execute(
                "SELECT payload FROM kw_cases WHERE case_id = %s FOR UPDATE", (case_id,),
            ).fetchone()
            case = _case_from_row(row)
            if case is None:
                return None
            changed = _apply_action(case, status, note, actor, auto_open=auto_open)
            db.execute(
                """UPDATE kw_cases SET payload = %s, updated_at = CURRENT_TIMESTAMP
                   WHERE case_id = %s""",
                (Jsonb(changed.model_dump(mode="json")), case_id),
            )
            return changed

    def apply_review_action(self, case_id: str, status: CaseStatus,
                            note: str | None = None, actor: str = "prototype_officer"
                            ) -> ComplianceCase | None:
        return self._transition(case_id, status, note, actor, auto_open=True)

    def update_status(self, case_id: str, status: CaseStatus,
                      note: str | None = None, actor: str = "prototype_officer"
                      ) -> ComplianceCase | None:
        return self._transition(case_id, status, note, actor, auto_open=False)


class PostgresAnalysisHistoryStore:
    def _append(self, centre_id: str, batch_id: str, analysis_type: str,
                outcome: str, summary: str, details: dict | None,
                *, edge_event_id: str | None = None) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        row = {
            "created_at": now, "centre_id": centre_id, "batch_id": batch_id,
            "analysis_type": analysis_type, "outcome": outcome,
            "summary": summary, "details": details or {},
        }
        with connection() as db:
            new = db.execute(
                """INSERT INTO kw_analysis_history(centre_id, batch_id, edge_event_id, payload)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT(edge_event_id) DO NOTHING
                   RETURNING id""",
                (centre_id, batch_id, edge_event_id, Jsonb(row)),
            ).fetchone()
            if new is None:
                new = db.execute(
                    "SELECT id, payload FROM kw_analysis_history WHERE edge_event_id = %s",
                    (edge_event_id,),
                ).fetchone()
                if new is None:
                    raise RuntimeError("Edge history uniqueness lookup failed")
                row = new["payload"]
            row = {**row, "analysis_id": f"AN-{new['id']:06d}"}
            return row

    def append(self, *, centre_id: str, batch_id: str, analysis_type: str,
               outcome: str, summary: str, details: dict | None = None) -> dict:
        return self._append(centre_id, batch_id, analysis_type, outcome, summary, details)

    def append_edge_once(self, *, edge_event_id: str, centre_id: str,
                         batch_id: str, analysis_type: str, outcome: str,
                         summary: str, details: dict | None = None) -> dict:
        if not edge_event_id:
            raise ValueError("Edge history requires a unique event ID")
        return self._append(centre_id, batch_id, analysis_type, outcome, summary,
                            {**(details or {}), "edge_event_id": edge_event_id},
                            edge_event_id=edge_event_id)

    def list(self, *, centre_id: str | None = None, batch_id: str | None = None,
             limit: int = 100) -> list[dict]:
        query = "SELECT id, payload FROM kw_analysis_history WHERE TRUE"
        args: list = []
        if centre_id:
            query += " AND centre_id = %s"
            args.append(centre_id)
        if batch_id:
            query += " AND batch_id = %s"
            args.append(batch_id)
        query += " ORDER BY id DESC LIMIT %s"
        args.append(max(1, limit))
        with connection() as db:
            rows = db.execute(query, args).fetchall()
        return [{**row["payload"], "analysis_id": f"AN-{row['id']:06d}"} for row in rows]


class PostgresCentreSettingsStore:
    def get(self, centre_id: str) -> dict:
        with connection() as db:
            row = db.execute(
                "SELECT payload FROM kw_centre_settings WHERE centre_id = %s",
                (centre_id,),
            ).fetchone()
        return {**DEFAULT_SETTINGS, **(row["payload"] if row else {})}

    def save(self, centre_id: str, payload: dict) -> dict:
        with connection() as db:
            # Avoid lost updates when different backend workers patch distinct
            # settings on the same centre at the same time.
            db.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s), %s)",
                (centre_id, 82630092),
            )
            row = db.execute(
                "SELECT payload FROM kw_centre_settings WHERE centre_id = %s",
                (centre_id,),
            ).fetchone()
            value = {**DEFAULT_SETTINGS, **(row["payload"] if row else {}), **payload}
            db.execute(
                """INSERT INTO kw_centre_settings(centre_id, payload)
                   VALUES(%s, %s)
                   ON CONFLICT(centre_id) DO UPDATE SET payload = EXCLUDED.payload""",
                (centre_id, Jsonb(value)),
            )
        return value


class PostgresEdgeEventLedger:
    def load(self) -> list[dict]:
        with connection() as db:
            rows = db.execute("SELECT payload FROM kw_edge_events ORDER BY received_order").fetchall()
        return [row["payload"] for row in rows]

    def save(self, rows: list[dict]) -> None:
        with connection() as db:
            for row in rows:
                db.execute(
                    """INSERT INTO kw_edge_events(event_id, payload)
                       VALUES(%s, %s) ON CONFLICT(event_id) DO NOTHING""",
                    (row["event_id"], Jsonb(row)),
                )
