"""Persisted local two-role Chatbox transport with centre-scoped demo membership.

Explicitly unavailable in protected deployments until real staff authentication
and provisioned chat storage replace synthetic role selection.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
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


# Voice media is stored outside any web-served static directory. A message id
# identifies a random file; client-controlled names and paths are never used.
import hashlib

MAX_VOICE_BYTES = 4 * 1024 * 1024
ALLOWED_VOICE = {"audio/webm": ("webm", b"\x1a\x45\xdf\xa3"),
                 "audio/ogg": ("ogg", b"OggS"),
                 "audio/mp4": ("mp4", None)}

def _voice_suffix(media_type: str, data: bytes) -> str:
    if media_type not in ALLOWED_VOICE:
        raise ValueError("Unsupported audio format")
    suffix, signature = ALLOWED_VOICE[media_type]
    if signature and not data.startswith(signature):
        raise ValueError("Audio does not match declared format")
    if media_type == "audio/mp4" and (len(data) < 12 or data[4:8] != b"ftyp"):
        raise ValueError("Audio does not match declared format")
    return suffix

def send_voice(path: Path, thread_id: str, actor_id: str, payload: bytes,
               media_type: str, duration_ms: int, idem: str) -> dict:
    thread=accessible_thread(thread_id,actor_id)
    if not thread:
        raise LookupError("Conversation not found")
    if not 16 <= len(payload) <= MAX_VOICE_BYTES:
        raise ValueError("Voice note must be between 16 bytes and 4 MB")
    if not isinstance(duration_ms,int) or not 100 <= duration_ms <= 60000:
        raise ValueError("Voice duration must be between 0.1 and 60 seconds")
    suffix=_voice_suffix(media_type,payload)
    if not (8 <= len(idem) <= 128) or not all(c.isalnum() or c in "-_" for c in idem):
        raise ValueError("Invalid message idempotency key")
    db=connect(path)
    uid=str(uuid4())
    folder=path.parent / "chatbox_voice"
    filename=folder / (uid + "." + suffix)
    created=False
    try:
        db.execute("BEGIN IMMEDIATE")
        duplicate=db.execute("SELECT * FROM chat_messages WHERE thread_id=? AND sender_id=? AND idempotency_key=?",
                (thread_id,actor_id,idem)).fetchone()
        if duplicate:
            db.commit()
            return view_message(duplicate)
        folder.mkdir(parents=True,exist_ok=True)
        # Exclusive file creation; the UUID cannot be submitted by callers.
        with filename.open("xb") as f:
            f.write(payload)
            f.flush()
            import os
            os.fsync(f.fileno())
        created=True
        now=datetime.now(timezone.utc).isoformat()
        digest=hashlib.sha256(payload).hexdigest()
        db.execute("""INSERT INTO chat_messages
            (id,thread_id,centre_id,sender_id,kind,body,media_key,
            content_type,duration_ms,byte_size,sha256,created_at_utc,idempotency_key)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (uid,thread_id,thread["centre_id"],actor_id,"voice",None,
             filename.name,media_type,duration_ms,len(payload),digest,now,idem))
        db.commit()
        row=db.execute("SELECT * FROM chat_messages WHERE id=?",(uid,)).fetchone()
        return view_message(row)
    except Exception:
        db.rollback()
        if created:
            filename.unlink(missing_ok=True)
        raise
    finally:
        db.close()

def read_voice(path: Path, message_id: str, actor_id: str) -> tuple[bytes,str]:
    db=connect(path)
    try:
        row=db.execute("SELECT * FROM chat_messages WHERE id=? AND kind='voice'",
                       (message_id,)).fetchone()
        if row is None or not accessible_thread(row["thread_id"],actor_id):
            raise LookupError("Voice note not found")
        key=row["media_key"]
        if not isinstance(key,str) or key not in {
            message_id+".webm", message_id+".ogg", message_id+".mp4"}:
            raise IOError("Untrusted media key")
        media=path.parent / "chatbox_voice" / key
        content=media.read_bytes()
        if len(content)!=row["byte_size"] or hashlib.sha256(content).hexdigest()!=row["sha256"]:
            raise IOError("Voice integrity check failed")
        _voice_suffix(row["content_type"],content)
        return content,row["content_type"]
    finally:
        db.close()
