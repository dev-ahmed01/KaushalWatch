"""Persisted local two-role Chatbox transport with centre-scoped demo membership.

Explicitly unavailable in protected deployments until real staff authentication
and provisioned chat storage replace synthetic role selection.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import hashlib
import os
import tempfile
from uuid import uuid4

from app.services.centre_desk import fixture_contacts
from app.services.demo_network import DEMO_CENTRES

MAX_TEXT_LENGTH = 2000

def participants(centre_id: str) -> list[dict]:
    return fixture_contacts(centre_id)

def member_by_id(actor_id: str) -> dict | None:
    for centre in DEMO_CENTRES:
        for actor in participants(centre["centre_id"]):
            if actor["id"] == actor_id:
                return actor
    return None

def demo_threads(centre_id: str) -> list[dict]:
    people = participants(centre_id)
    officer = next(p for p in people if p["role"] == "officer")
    return [
        {"id": "thread-" + centre_id + "-head", "centre_id": centre_id,
         "participant_ids": [officer["id"], next(p["id"] for p in people if p["role"] == "centre_head")],
         "topic": "Centre head", "simulated": True},
        {"id": "thread-" + centre_id + "-trainer", "centre_id": centre_id,
         "participant_ids": [officer["id"], next(p["id"] for p in people if p["role"] == "trainer")],
         "topic": "Trainer", "simulated": True},
    ]

def accessible_thread(thread_id: str, actor_id: str) -> dict | None:
    member = member_by_id(actor_id)
    if not member:
        return None
    return next((t for t in demo_threads(member["centre_id"])
                 if t["id"] == thread_id and actor_id in t["participant_ids"]), None)

def connect(path: Path):
    path.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(path,timeout=10.0)
    db.row_factory=sqlite3.Row
    db.execute("PRAGMA busy_timeout=10000")
    db.execute("""CREATE TABLE IF NOT EXISTS chat_messages (
        id TEXT PRIMARY KEY, thread_id TEXT NOT NULL, centre_id TEXT NOT NULL,
        sender_id TEXT NOT NULL, kind TEXT NOT NULL,
        body TEXT, media_key TEXT, content_type TEXT, duration_ms INTEGER,
        byte_size INTEGER, sha256 TEXT, created_at_utc TEXT NOT NULL,
        idempotency_key TEXT NOT NULL,
        UNIQUE(thread_id, sender_id, idempotency_key))""")
    db.execute("CREATE INDEX IF NOT EXISTS chat_thread_history ON chat_messages(thread_id, created_at_utc, id)")
    return db

def view_message(row) -> dict:
    return {"id":row["id"],"thread_id":row["thread_id"],"sender_id":row["sender_id"],
            "kind":row["kind"],"body":row["body"],"created_at_utc":row["created_at_utc"],
            "duration_ms":row["duration_ms"],"byte_size":row["byte_size"],
            "content_type":row["content_type"],"sha256":row["sha256"],"simulated":True}

def list_messages(path: Path, thread_id: str, actor_id: str, limit: int = 75) -> list[dict]:
    if not accessible_thread(thread_id,actor_id):
        raise LookupError("Conversation not found")
    db=connect(path)
    try:
        rows=db.execute("""SELECT * FROM (
            SELECT * FROM chat_messages WHERE thread_id=?
            ORDER BY created_at_utc DESC, id DESC LIMIT ?)
            ORDER BY created_at_utc ASC, id ASC""",(thread_id,min(100,max(1,limit)))).fetchall()
        return [view_message(row) for row in rows]
    finally:
        db.close()

def list_threads(path: Path, actor_id: str) -> dict:
    actor=member_by_id(actor_id)
    if not actor:
        raise LookupError("Demo role not found")
    people=participants(actor["centre_id"])
    db=connect(path)
    try:
        rows=[]
        for thread in demo_threads(actor["centre_id"]):
            if actor_id not in thread["participant_ids"]:
                continue
            last=db.execute("SELECT * FROM chat_messages WHERE thread_id=? ORDER BY created_at_utc DESC,id DESC LIMIT 1",(thread["id"],)).fetchone()
            peer=next(p for p in people if p["id"] != actor_id and p["id"] in thread["participant_ids"])
            rows.append({**thread,"peer":peer,"last_message":view_message(last) if last else None,
                         "unread_count":None})
        rows.sort(key=lambda t: t["last_message"]["created_at_utc"] if t["last_message"] else "",reverse=True)
        return {"actor":actor,"people":people,"roles":people,
                "threads":rows,"centre_id":actor["centre_id"],"simulated":True}
    finally:
        db.close()

def send_text(path: Path, thread_id: str, actor_id: str, text: str, idem: str) -> dict:
    thread=accessible_thread(thread_id,actor_id)
    if not thread:
        raise LookupError("Conversation not found")
    body=text.strip()
    if not body or len(body)>MAX_TEXT_LENGTH:
        raise ValueError("Message must have 1–2000 characters")
    if not (8<=len(idem)<=128) or not all(c.isalnum() or c in "-_" for c in idem):
        raise ValueError("Invalid message idempotency key")
    db=connect(path)
    try:
        db.execute("BEGIN IMMEDIATE")
        duplicate=db.execute("SELECT * FROM chat_messages WHERE thread_id=? AND sender_id=? AND idempotency_key=?",
                             (thread_id,actor_id,idem)).fetchone()
        if duplicate:
            db.commit()
            return view_message(duplicate)
        uid=str(uuid4())
        now=datetime.now(timezone.utc).isoformat()
        db.execute("""INSERT INTO chat_messages
             (id,thread_id,centre_id,sender_id,kind,body,created_at_utc,idempotency_key)
             VALUES (?,?,?,?,?,?,?,?)""",
             (uid,thread_id,thread["centre_id"],actor_id,"text",body,now,idem))
        db.commit()
        row=db.execute("SELECT * FROM chat_messages WHERE id=?",(uid,)).fetchone()
        return view_message(row)
    finally:
        db.close()

VOICE_LIMIT_BYTES = 8 * 1024 * 1024
VOICE_LIMIT_DURATION_MS = 90000
VOICE_SIGNATURES = {
    "audio/webm": (".webm", lambda b: b.startswith(bytes.fromhex("1a45dfa3"))),
    "audio/ogg": (".ogg", lambda b: b.startswith(b"OggS")),
    "audio/mp4": (".m4a", lambda b: len(b) > 12 and b[4:8] == b"ftyp"),
    "audio/wav": (".wav", lambda b: b.startswith(b"RIFF") and b[8:12] == b"WAVE"),
}

def save_voice(path: Path, media_dir: Path, thread_id: str, actor_id: str, data: bytes,
               mime: str, duration_ms: int, idem: str) -> dict:
    thread=accessible_thread(thread_id,actor_id)
    if not thread:
        raise LookupError("Conversation not found")
    content_type=mime.lower().split(";",1)[0].strip()
    kind=VOICE_SIGNATURES.get(content_type)
    if kind is None or not kind[1](data):
        raise ValueError("Unsupported or mismatched audio file")
    if not data or len(data)>VOICE_LIMIT_BYTES:
        raise ValueError("Voice note exceeds the size limit")
    if not isinstance(duration_ms,int) or isinstance(duration_ms,bool) or not 1<=duration_ms<=VOICE_LIMIT_DURATION_MS:
        raise ValueError("Voice note duration is out of bounds")
    if not (8<=len(idem)<=128) or not all(c.isalnum() or c in "-_" for c in idem):
        raise ValueError("Invalid idempotency key")
    db=connect(path)
    temp: Path|None=None
    asset: Path|None=None
    try:
        db.execute("BEGIN IMMEDIATE")
        existing=db.execute("SELECT * FROM chat_messages WHERE thread_id=? AND sender_id=? AND idempotency_key=?",
                            (thread_id,actor_id,idem)).fetchone()
        if existing:
            db.commit()
            return view_message(existing)
        media_dir.mkdir(parents=True,exist_ok=True)
        uid=str(uuid4())
        media_key=uid+kind[0]
        asset=media_dir/media_key
        sha=hashlib.sha256(data).hexdigest()
        with tempfile.NamedTemporaryFile(dir=media_dir,prefix=".chat-voice-",suffix=".tmp",delete=False) as handle:
            temp=Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
            os.chmod(temp,0o600)
        os.replace(temp,asset)
        temp=None
        now=datetime.now(timezone.utc).isoformat()
        db.execute("""INSERT INTO chat_messages
            (id,thread_id,centre_id,sender_id,kind,body,media_key,content_type,duration_ms,byte_size,sha256,created_at_utc,idempotency_key)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (uid,thread_id,thread["centre_id"],actor_id,"voice",None,media_key,content_type,
             duration_ms,len(data),sha,now,idem))
        db.commit()
        return view_message(db.execute("SELECT * FROM chat_messages WHERE id=?",(uid,)).fetchone())
    except Exception:
        db.rollback()
        if asset is not None:
            asset.unlink(missing_ok=True)
        raise
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)
        db.close()

def get_voice(path: Path, media_dir: Path, thread_id: str, actor_id: str, message_id: str) -> tuple[bytes,str]:
    if not accessible_thread(thread_id,actor_id):
        raise LookupError("Voice note not found")
    db=connect(path)
    try:
        row=db.execute("""SELECT media_key,content_type,sha256,byte_size FROM chat_messages
            WHERE id=? AND thread_id=? AND kind='voice'""",(message_id,thread_id)).fetchone()
    finally:
        db.close()
    if not row or not row["media_key"] or not row["sha256"]:
        raise LookupError("Voice note not found")
    # Only server-generated UUID file names are ever read; reject old/corrupt path rows.
    if not (len(row["media_key"])>=38 and row["media_key"][:36]==message_id
            and row["media_key"][36:] in {".webm",".m4a",".ogg",".wav"}):
        raise LookupError("Voice note not found")
    try:
        raw=(media_dir/row["media_key"]).read_bytes()
    except OSError as exc:
        raise RuntimeError("Private voice asset unavailable") from exc
    if len(raw)!=row["byte_size"] or hashlib.sha256(raw).hexdigest()!=row["sha256"]:
        raise RuntimeError("Private voice integrity check failed")
    return raw,row["content_type"]
