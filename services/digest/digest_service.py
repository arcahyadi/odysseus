"""
services/digest/digest_service.py

Auto-digest: daily activity summarisation via LLM.
Requirements: 6.1–6.10, 7.1–7.3
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, date, timedelta, timezone
from typing import Dict, List, Optional, Any

from core.database import Digest, SessionLocal

logger = logging.getLogger(__name__)

_DIGEST_SYSTEM = """You are a personal assistant summarising the user's day.
Given a day's activity (chats, notes, emails), produce a JSON object with exactly these keys:
  "highlights": [str, ...]       -- key events or decisions (up to 8 items)
  "action_items": [str, ...]     -- follow-up tasks identified (up to 10 items)
  "open_questions": [str, ...]   -- unresolved questions or blockers
  "tone_summary": str            -- 1-3 sentence mood/productivity characterisation
Return ONLY valid JSON, no markdown fences."""


class DigestService:

    def __init__(self, db_factory=None):
        self._db = db_factory or SessionLocal

    # ── Collection ────────────────────────────────────────────────────────────

    def _collect_day(self, db, owner: str, target_date: date) -> str:
        """Build plain-text string of the day's activity."""
        from core.database import ChatMessage, Session as DbSession
        start = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0)
        end = start + timedelta(days=1)
        try:
            messages = (
                db.query(ChatMessage)
                .join(DbSession, ChatMessage.session_id == DbSession.id)
                .filter(
                    DbSession.owner == owner,
                    ChatMessage.timestamp >= start,
                    ChatMessage.timestamp < end,
                    ChatMessage.role.in_(["user", "assistant"]),
                )
                .order_by(ChatMessage.timestamp)
                .all()
            )
        except Exception:
            messages = []
        lines = [f"[{m.role.upper()}] {(m.content or '')[:500]}" for m in messages]
        return "\n".join(lines) if lines else "(no activity)"

    # ── Generation ────────────────────────────────────────────────────────────

    async def generate(
        self,
        owner: str,
        target_date: Optional[date] = None,
        endpoint_url: str = "",
        model: str = "",
        headers: Optional[Dict] = None,
        digest_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate and persist a digest. Requirements: 6.1–6.5, 6.9

        endpoint_url/model are used verbatim - this method does NOT resolve a
        default. Callers must supply one (digest_routes resolves via
        resolve_task_endpoint) or the httpx call fails and the row is marked
        status="failed".

        digest_id lets a caller pre-allocate the row id, so an async 202
        response can hand back an id that will actually match the persisted row.
        Ignored when a row for (owner, date) already exists.
        """
        if target_date is None:
            target_date = (datetime.now(timezone.utc) - timedelta(days=1)).date()
        date_str = target_date.isoformat()
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        db = self._db()
        try:
            existing = db.query(Digest).filter_by(owner=owner, date=date_str).first()
            if existing:
                digest_id = existing.id
                existing.status = "pending"
                existing.updated_at = now
            else:
                digest_id = digest_id or str(uuid.uuid4())
                existing = Digest(
                    id=digest_id, owner=owner, date=date_str,
                    status="pending", created_at=now, updated_at=now,
                )
                db.add(existing)
            db.commit()
            activity_text = self._collect_day(db, owner, target_date)
        finally:
            db.close()

        try:
            import httpx
            url = endpoint_url.rstrip("/")
            if "/v1" not in url:
                url += "/v1"
            url += "/chat/completions"
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": _DIGEST_SYSTEM},
                    {"role": "user", "content": f"Date: {date_str}\n\n{activity_text}"},
                ],
                "temperature": 0.3,
                "max_tokens": 1200,
            }
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(url, json=payload, headers=headers or {})
                resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"].strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            parsed: Dict = json.loads(raw)
            for key in ("highlights", "action_items", "open_questions", "tone_summary"):
                if key not in parsed:
                    parsed[key] = [] if key != "tone_summary" else ""
        except Exception as exc:
            db2 = self._db()
            try:
                row = db2.query(Digest).filter_by(id=digest_id).first()
                if row:
                    row.status = "failed"
                    row.error = str(exc)
                    row.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    db2.commit()
            finally:
                db2.close()
            logger.error("Digest LLM call failed for %s/%s: %s", owner, date_str, exc)
            return {"status": "failed", "error": str(exc)}

        db3 = self._db()
        try:
            row = db3.query(Digest).filter_by(id=digest_id).first()
            if row:
                row.content = json.dumps(parsed, ensure_ascii=False)
                row.summary = parsed.get("tone_summary", "")
                row.status = "complete"
                row.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                db3.commit()
        finally:
            db3.close()

        return {"status": "complete", "date": date_str, "content": parsed}

    def pending_id(self, owner: str, target_date: Optional[date] = None) -> str:
        """Return the id generate() will use for (owner, target_date).

        generate() upserts by (owner, date) and only mints a uuid when no row
        exists yet. A route that returned its own fresh uuid would therefore name
        a row that never appears and could not be polled. Ask this first, pass
        the answer back as generate(digest_id=...), and the two agree.
        """
        if target_date is None:
            target_date = (datetime.now(timezone.utc) - timedelta(days=1)).date()
        date_str = target_date.isoformat()
        db = self._db()
        try:
            row = db.query(Digest).filter_by(owner=owner, date=date_str).first()
            return row.id if row else str(uuid.uuid4())
        finally:
            db.close()

    # ── Retrieval ─────────────────────────────────────────────────────────────

    def list_digests(self, owner: str, limit: int = 30, offset: int = 0) -> List[Dict]:
        """Req 6.6"""
        db = self._db()
        try:
            rows = (
                db.query(Digest)
                .filter_by(owner=owner)
                .order_by(Digest.date.desc())
                .offset(offset).limit(limit).all()
            )
            return [self._digest_to_dict(r) for r in rows]
        finally:
            db.close()

    def get_by_date(self, owner: str, date_str: str) -> Optional[Dict]:
        """Req 6.7"""
        db = self._db()
        try:
            row = db.query(Digest).filter_by(owner=owner, date=date_str).first()
            return self._digest_to_dict(row) if row else None
        finally:
            db.close()

    def search(self, owner: str, q: str) -> List[Dict]:
        """Full-text search over digest content + summary. Req 7.1"""
        if not q or not q.strip():
            return []
        q_lower = q.lower()
        db = self._db()
        try:
            rows = (
                db.query(Digest)
                .filter(Digest.owner == owner)
                .order_by(Digest.date.desc())
                .all()
            )
            return [
                self._digest_to_dict(r) for r in rows
                if q_lower in (r.content or "").lower()
                or q_lower in (r.summary or "").lower()
            ]
        finally:
            db.close()

    @staticmethod
    def _digest_to_dict(r: Digest) -> Dict:
        content = None
        if r.content:
            try:
                content = json.loads(r.content)
            except json.JSONDecodeError:
                content = r.content
        return {
            "id": r.id, "date": r.date, "status": r.status,
            "summary": r.summary, "content": content, "error": r.error,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }


# Module-level singleton
digest_service = DigestService()


# ── Morning Digest ─────────────────────────────────────────────────────────────

_MORNING_SYSTEM = """You are the user's personal assistant delivering their morning briefing.

You will receive today's calendar events, unread email count with recent sender/subject lines,
and a list of open to-do items. Produce a warm, concise spoken-style briefing in plain prose
(no bullet points, no markdown). Structure:

1. A one-sentence greeting acknowledging the day and date.
2. Calendar summary — weave events naturally into the sentence (e.g. "You have a team standup at 9").
3. Email summary — mention unread count and highlight any notable senders/subjects.
4. Todos — name any open tasks, keeping it brief.
5. A closing one-liner with a focus suggestion or motivational note.

Keep the total under 120 words. Speak directly to the user as "you". No headers, no lists."""

_MORNING_JSON_SYSTEM = """You are a personal assistant preparing a morning briefing for the user.

Given today's calendar events, email status, and open todos, return a JSON object with:
  "narrative":  str   -- warm 2-4 sentence spoken-style summary (no markdown, under 120 words)
  "calendar":   [{"time": "HH:MM"|"all day", "title": str, "location": str|null}]  -- today's events
  "email":      {"unread": int, "highlights": [{"from": str, "subject": str}]}
  "todos":      [str]   -- open todo item titles (up to 8)
  "focus":      str     -- one short sentence: suggested priority for the day

Return ONLY valid JSON, no markdown fences."""


def _collect_morning_data(owner: str) -> dict:
    """Collect calendar, email, and todo data for the morning digest.

    Uses in-process DB queries (calendar, notes) and the local email index
    (no live IMAP connection needed) so it is fast and works offline.
    """
    from datetime import datetime as _dt, timedelta as _td
    import json as _json

    # ── allow_null gate (single-user compat) ─────────────────────────
    try:
        from core.auth import AuthManager
        _allow_null = not AuthManager().is_configured
    except Exception:
        _allow_null = False

    result: dict = {"calendar": [], "email": {"unread": 0, "highlights": []}, "todos": []}

    # ── Calendar ─────────────────────────────────────────────────────
    try:
        from core.database import SessionLocal as _SL, CalendarEvent as _CE, CalendarCal as _CC
        today = _dt.now().replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today + _td(days=1)
        _db = _SL()
        try:
            ev_q = (
                _db.query(_CE)
                .join(_CC, _CE.calendar_id == _CC.id)
                .filter(
                    _CE.dtstart < tomorrow,
                    _CE.dtend > today,
                    _CE.status != "cancelled",
                )
            )
            if owner:
                from src.auth_helpers import owner_filter
                ev_q = owner_filter(ev_q, _CC, owner, include_shared=_allow_null)
            events = ev_q.order_by(_CE.dtstart).all()
            for ev in events:
                if ev.all_day:
                    t = "all day"
                else:
                    try:
                        t = ev.dtstart.strftime("%H:%M")
                    except Exception:
                        t = ""
                result["calendar"].append({
                    "time": t,
                    "title": ev.summary or "",
                    "location": ev.location or None,
                })
        finally:
            _db.close()
    except Exception as exc:
        logger.debug("morning_digest: calendar collection failed: %s", exc)

    # ── Email (local index first, IMAP fallback) ──────────────────────
    try:
        import sqlite3 as _sql3
        from core.constants import DATA_DIR as _DATA
        import os as _os
        _sched_db = _os.path.join(_DATA, "scheduled_tasks.db")
        if _os.path.exists(_sched_db):
            _conn = _sql3.connect(_sched_db)
            try:
                _row = _conn.execute(
                    """SELECT COUNT(*) FROM email_message_index
                       WHERE owner=? AND folder='INBOX'
                         AND (flags IS NULL OR instr(flags,'\\Seen')=0)""",
                    (owner or "",),
                ).fetchone()
                result["email"]["unread"] = int((_row or [0])[0] or 0)
                # Top 5 unread by uid desc
                _rows = _conn.execute(
                    """SELECT sender, subject FROM email_message_index
                       WHERE owner=? AND folder='INBOX'
                         AND (flags IS NULL OR instr(flags,'\\Seen')=0)
                       ORDER BY CAST(uid AS INTEGER) DESC LIMIT 5""",
                    (owner or "",),
                ).fetchall()
                for sender, subject in _rows:
                    import email.utils as _eu
                    name, _ = _eu.parseaddr(sender or "")
                    result["email"]["highlights"].append({
                        "from": name or sender or "?",
                        "subject": (subject or "").strip() or "(no subject)",
                    })
            finally:
                _conn.close()
    except Exception as exc:
        logger.debug("morning_digest: email index lookup failed: %s", exc)
        # Fallback: raw IMAP (best-effort)
        try:
            import email as _email_lib
            from routes.email_helpers import _imap_connect, _decode_header
            _conn2 = _imap_connect(None)
            try:
                _conn2.select("INBOX", readonly=True)
                _status, _data = _conn2.search(None, "UNSEEN")
                _uids = (_data[0].split() if _status == "OK" and _data and _data[0] else [])
                result["email"]["unread"] = len(_uids)
                for _uid in _uids[-5:][::-1]:
                    try:
                        _, _msg_data = _conn2.fetch(_uid, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])")
                        if not _msg_data or not _msg_data[0]:
                            continue
                        _hdr = _msg_data[0][1] if isinstance(_msg_data[0], tuple) else _msg_data[0]
                        _parsed = _email_lib.message_from_bytes(_hdr)
                        _subj = _decode_header(_parsed.get("Subject") or "") or "(no subject)"
                        _from = _decode_header(_parsed.get("From") or "") or "?"
                        if "<" in _from:
                            _from = _from.split("<", 1)[0].strip().strip('"') or _from
                        result["email"]["highlights"].append({"from": _from, "subject": _subj})
                    except Exception:
                        pass
            finally:
                try:
                    _conn2.logout()
                except Exception:
                    pass
        except Exception as exc2:
            logger.debug("morning_digest: IMAP fallback also failed: %s", exc2)

    # ── Todos ─────────────────────────────────────────────────────────
    try:
        from core.database import SessionLocal as _SL2, Note as _Note
        _db2 = _SL2()
        try:
            n_q = _db2.query(_Note).filter(_Note.archived == False)  # noqa: E712
            if owner:
                from src.auth_helpers import owner_filter
                n_q = owner_filter(n_q, _Note, owner, include_shared=_allow_null)
            notes = n_q.all()
        finally:
            _db2.close()
        import json as _j
        for n in notes:
            if n.note_type == "checklist" and n.items:
                try:
                    items = _j.loads(n.items)
                    for it in items:
                        if not it.get("done") and it.get("text"):
                            label = f"{n.title or 'Task'}: {it['text']}"
                            result["todos"].append(label)
                            if len(result["todos"]) >= 8:
                                break
                except Exception:
                    pass
            elif n.pinned and n.title and not n.archived:
                result["todos"].append(n.title)
            if len(result["todos"]) >= 8:
                break
    except Exception as exc:
        logger.debug("morning_digest: todos collection failed: %s", exc)

    return result


class MorningDigestService:
    """Generate and persist a rich, LLM-synthesised morning briefing.

    Extends the existing DigestService storage layer — morning digests are
    stored in the same `digests` table with ``date`` set to today's date.
    The ``content`` JSON gains extra keys: ``narrative``, ``calendar``,
    ``email``, ``todos``, ``focus``.
    """

    def __init__(self, db_factory=None):
        self._db = db_factory or SessionLocal

    async def generate(self, owner: str) -> dict:
        """Collect data, synthesise with LLM, persist to Digest table."""
        from datetime import datetime as _dt, timezone as _tz
        from src.task_endpoint import resolve_task_endpoint
        from src.llm_core import llm_call_async
        from src.text_helpers import strip_think

        today_str = _dt.now().strftime("%Y-%m-%d")
        day_label = _dt.now().strftime("%A, %B %-d, %Y") if hasattr(_dt, "strftime") else _dt.now().strftime("%A, %B %d, %Y")
        # strftime %-d (no-zero-pad day) is glibc-only; safe fallback:
        try:
            day_label = _dt.now().strftime(f"%A, %B {_dt.now().day}, %Y")
        except Exception:
            pass

        now = _dt.now(_tz.utc).replace(tzinfo=None)

        # ── Upsert a "pending" Digest row ─────────────────────────────
        db = self._db()
        try:
            existing = db.query(Digest).filter_by(owner=owner, date=today_str).first()
            if existing:
                digest_id = existing.id
                existing.status = "pending"
                existing.updated_at = now
            else:
                digest_id = str(uuid.uuid4())
                existing = Digest(
                    id=digest_id, owner=owner, date=today_str,
                    status="pending", created_at=now, updated_at=now,
                )
                db.add(existing)
            db.commit()
        finally:
            db.close()

        # ── Collect raw data ──────────────────────────────────────────
        data = _collect_morning_data(owner)

        # ── Build user message for LLM ───────────────────────────────
        import json as _j
        cal_lines = []
        for ev in data["calendar"]:
            loc = f" @ {ev['location']}" if ev.get("location") else ""
            cal_lines.append(f"  {ev['time']}  {ev['title']}{loc}")
        email_lines = [f"  Unread: {data['email']['unread']}"]
        for h in data["email"]["highlights"]:
            email_lines.append(f"  · {h['from']} — {h['subject']}")
        todo_lines = [f"  · {t}" for t in data["todos"]]

        user_msg = (
            f"Date: {day_label}\n\n"
            f"CALENDAR ({len(data['calendar'])} events):\n" +
            ("\n".join(cal_lines) if cal_lines else "  (nothing scheduled)") +
            f"\n\nEMAIL:\n" +
            "\n".join(email_lines) +
            f"\n\nOPEN TODOS ({len(data['todos'])}):\n" +
            ("\n".join(todo_lines) if todo_lines else "  (none)")
        )

        # ── LLM synthesis ─────────────────────────────────────────────
        parsed: dict = {}
        try:
            url, model, headers = resolve_task_endpoint(
                endpoint_url=None, model=None, headers=None, owner=owner
            )
            if not url or not model:
                raise RuntimeError("No utility/default model configured")

            raw = await llm_call_async(
                url=url,
                model=model,
                messages=[
                    {"role": "system", "content": _MORNING_JSON_SYSTEM},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.55,
                max_tokens=800,
                headers=headers or {},
                workload="background",
                timeout=90,
            )
            raw = strip_think(raw or "", prose=True, prompt_echo=True).strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            parsed = _j.loads(raw)
            # Ensure all expected keys exist
            parsed.setdefault("narrative", "")
            parsed.setdefault("calendar", data["calendar"])
            parsed.setdefault("email", data["email"])
            parsed.setdefault("todos", data["todos"])
            parsed.setdefault("focus", "")
        except Exception as exc:
            logger.warning("morning_digest: LLM synthesis failed (%s); using plain fallback", exc)
            # Graceful fallback: assemble narrative from raw data
            parts = [f"Good morning! Here's your briefing for {day_label}."]
            if data["calendar"]:
                ev = data["calendar"][0]
                parts.append(f"You have {len(data['calendar'])} calendar event(s), starting with '{ev['title']}' at {ev['time']}.")
            if data["email"]["unread"]:
                parts.append(f"You have {data['email']['unread']} unread email(s).")
            if data["todos"]:
                parts.append(f"Open todos: {', '.join(data['todos'][:3])}.")
            parsed = {
                "narrative": " ".join(parts),
                "calendar": data["calendar"],
                "email": data["email"],
                "todos": data["todos"],
                "focus": "",
                "_fallback": True,
            }

        # ── Persist ───────────────────────────────────────────────────
        db2 = self._db()
        try:
            row = db2.query(Digest).filter_by(id=digest_id).first()
            if row:
                row.content = _j.dumps(parsed, ensure_ascii=False)
                row.summary = parsed.get("narrative", "")[:500]
                row.status = "complete"
                row.updated_at = _dt.now(_tz.utc).replace(tzinfo=None)
                db2.commit()
        finally:
            db2.close()

        return {"status": "complete", "date": today_str, "content": parsed}

    def get_today(self, owner: str) -> Optional[Dict]:
        """Return today's morning digest if it exists, else None."""
        from datetime import datetime as _dt
        today_str = _dt.now().strftime("%Y-%m-%d")
        db = self._db()
        try:
            row = db.query(Digest).filter_by(owner=owner, date=today_str).first()
            if row is None:
                return None
            content = None
            if row.content:
                try:
                    content = json.loads(row.content)
                except json.JSONDecodeError:
                    content = row.content
            return {
                "id": row.id,
                "date": row.date,
                "status": row.status,
                "summary": row.summary,
                "content": content,
                "error": row.error,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
        finally:
            db.close()


# Module-level morning digest singleton
morning_digest_service = MorningDigestService()
