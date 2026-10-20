"""Local controlled Centre Desk: synthetic batches and durable operator task events.

No inferred trainee identity, no camera-derived individual attendance and no
protected/pilot fixture fallback. SQLite is scoped to the local demo workspace.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import sqlite3

from app.services.demo_network import DEMO_CENTRES

IST = ZoneInfo("Asia/Kolkata")
TASK_STATES = frozenset({"pending", "acknowledged", "resolved"})
CATEGORIES = ("trainer", "equipment", "attendance")
TASK_DESCRIPTIONS = {
    "trainer": "Confirm trainer assignment and availability",
    "equipment": "Complete the lab readiness checklist",
    "attendance": "Review roster follow-up records",
}

def today_ist() -> str:
    return datetime.now(IST).date().isoformat()

def fixture_contacts(centre_id: str) -> list[dict]:
    return [
        {"id": "demo-head-" + centre_id, "centre_id": centre_id, "name": "Demo centre head", "role": "centre_head", "simulated": True},
        {"id": "demo-trainer-" + centre_id, "centre_id": centre_id, "name": "Demo lead trainer", "role": "trainer", "simulated": True},
        {"id": "demo-officer-" + centre_id, "centre_id": centre_id, "name": "Demo review officer", "role": "officer", "simulated": True},
    ]

def fixture_tasks(centre_id: str) -> list[dict]:
    return [
        {"id": "task-" + centre_id + "-" + kind, "centre_id": centre_id,
         "category": kind, "title": TASK_DESCRIPTIONS[kind],
         "status": "pending", "updated_at_utc": None, "simulated": True}
        for kind in CATEGORIES
    ]

def _db(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10.0)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA busy_timeout=10000")
    db.execute("""CREATE TABLE IF NOT EXISTS task_status (
        task_id TEXT PRIMARY KEY, centre_id TEXT NOT NULL,
        status TEXT NOT NULL, updated_at_utc TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS task_audit (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id TEXT NOT NULL, centre_id TEXT NOT NULL, previous_status TEXT NOT NULL,
        new_status TEXT NOT NULL, actor TEXT NOT NULL, occurred_at_utc TEXT NOT NULL)""")
    return db

def _tasks(path: Path, centre_id: str) -> list[dict]:
    tasks = fixture_tasks(centre_id)
    db = _db(path)
    try:
        rows = {r["task_id"]: r for r in db.execute(
            "SELECT task_id, status, updated_at_utc FROM task_status WHERE centre_id=?",
            (centre_id,)).fetchall()}
        for task in tasks:
            row = rows.get(task["id"])
            if row:
                task["status"] = row["status"]
                task["updated_at_utc"] = row["updated_at_utc"]
    finally:
        db.close()
    return tasks

def centre_day(path: Path, centre: dict) -> dict:
    cid = centre["centre_id"]
    local_day = today_ist()
    tasks = _tasks(path, cid)
    batches = [
        {"id": "batch-" + cid + "-morning", "centre_id": cid,
         "date_local": local_day, "starts_at_ist": "09:30", "ends_at_ist": "12:30",
         "trade": centre["job_role"], "trainer_id": "demo-trainer-" + cid,
         "participant_count": centre["trainees"], "readiness": "scheduled", "simulated": True},
        {"id": "batch-" + cid + "-afternoon", "centre_id": cid,
         "date_local": local_day, "starts_at_ist": "13:30", "ends_at_ist": "16:30",
         "trade": centre["job_role"], "trainer_id": "demo-trainer-" + cid,
         "participant_count": centre["trainees"], "readiness": "scheduled", "simulated": True},
    ]
    contacts = fixture_contacts(cid)
    return {
        "centre_id": cid, "centre_name": centre["name"], "date_local": local_day,
        "timezone": "Asia/Kolkata", "simulated": True, "fixture_origin": "controlled_demo",
        "last_refreshed_at_utc": datetime.now(timezone.utc).isoformat(),
        "batches": batches, "tasks": tasks, "contacts": contacts,
        "counts": {
            "batches_today": len(batches),
            "trainers_present": None,  # No real check-in source.
            "equipment_alerts": sum(x["status"] != "resolved" for x in tasks if x["category"] == "equipment"),
            "attendance_followups": sum(x["status"] != "resolved" for x in tasks if x["category"] == "attendance"),
            "messages_pending": None,  # Real Chatbox receipts not connected until R5.
        },
    }

def change_task(path: Path, centre_id: str, task_id: str, status: str, actor="demo-operator") -> dict:
    if status not in TASK_STATES:
        raise ValueError("Unsupported task status")
    fixture = {row["id"]: row for row in fixture_tasks(centre_id)}
    if task_id not in fixture:
        raise LookupError("Task not found")
    now = datetime.now(timezone.utc).isoformat()
    db = _db(path)
    try:
        db.execute("BEGIN IMMEDIATE")
        current = db.execute("SELECT status FROM task_status WHERE task_id=? AND centre_id=?",
                             (task_id, centre_id)).fetchone()
        previous = current["status"] if current else "pending"
        if previous == "resolved" and status != "resolved":
            raise ValueError("Resolved tasks cannot be silently reopened")
        if status != previous:
            db.execute("""INSERT INTO task_status (task_id, centre_id, status, updated_at_utc)
                VALUES (?, ?, ?, ?) ON CONFLICT(task_id) DO UPDATE SET
                status=excluded.status, updated_at_utc=excluded.updated_at_utc""",
                (task_id, centre_id, status, now))
            db.execute("""INSERT INTO task_audit
                (task_id, centre_id, previous_status, new_status, actor, occurred_at_utc)
                VALUES (?, ?, ?, ?, ?, ?)""", (task_id, centre_id, previous, status, actor, now))
        db.commit()
    finally:
        db.close()
    return next(x for x in _tasks(path, centre_id) if x["id"] == task_id)

def task_history(path: Path, centre_id: str, task_id: str) -> list[dict]:
    db = _db(path)
    try:
        return [dict(x) for x in db.execute("""SELECT previous_status, new_status, actor, occurred_at_utc
            FROM task_audit WHERE centre_id=? AND task_id=? ORDER BY event_id ASC""",
            (centre_id, task_id)).fetchall()]
    finally:
        db.close()
