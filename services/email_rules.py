"""
services/email_rules.py

Trigger-based email automation rules.

A rule matches an incoming email dict and declares actions. The rule engine
is pure and side-effect free; action execution is a separate, injectable step
so callers (poller hooks, scheduled actions, or the /api/email-rules/evaluate
endpoint) decide when to apply side effects.

Rules persisted as `EmailRule` rows in core.database. Matchers and actions are
JSON columns so new predicate/action kinds can ship without schema changes.

Action vocabulary (advisory by default — they gate behaviour that the existing
email pipelines already provide):
  - summarize   → ensure the email is summarized (auto-summarize pass)
  - create_task → execute_rule_actions() inserts a checklist Note as a task
  - draft_reply → the AI auto-reply pass should draft a reply
  - add_event   → the email → calendar event extractor should scan this email
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List

logger = logging.getLogger(__name__)

VALID_ACTIONS = {"summarize", "create_task", "draft_reply", "add_event"}
# Matchers that may be empty (match-all when all empty).
MATCHER_KEYS = ("sender_contains", "subject_contains", "body_contains", "folder")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def rule_matches(rule: Dict, email: Dict) -> bool:
    """Return True if *email* satisfies every matcher on *rule*.

    Email dict keys consumed: sender (from), subject, body/snippet, folder.
    Empty matchers match anything. Matching is case-insensitive substring.
    """
    matchers = rule.get("matchers") or {}
    if isinstance(matchers, str):
        try:
            matchers = json.loads(matchers)
        except json.JSONDecodeError:
            matchers = {}

    sender = (email.get("sender") or email.get("from") or "").lower()
    subject = (email.get("subject") or "").lower()
    body = (email.get("body") or email.get("snippet") or email.get("content") or "").lower()
    folder = (email.get("folder") or "INBOX").lower()

    if matchers.get("sender_contains"):
        if matchers["sender_contains"].lower() not in sender:
            return False
    if matchers.get("subject_contains"):
        if matchers["subject_contains"].lower() not in subject:
            return False
    if matchers.get("body_contains"):
        if matchers["body_contains"].lower() not in body:
            return False
    if matchers.get("folder"):
        if matchers["folder"].lower() != folder:
            return False
    return True


def parse_actions(raw) -> List[str]:
    """Normalise a rule's action list to VALID_ACTIONS subset."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return []
    if not isinstance(raw, list):
        return []
    return [a for a in raw if a in VALID_ACTIONS]


class RuleEngine:
    """Match rules against an email. Pure; safe to unit test."""

    def __init__(self, rules_loader=None):
        # rules_loader(owner) -> list of rule dicts (persisted shape).
        self._loader = rules_loader or (lambda owner: [])

    def load_rules(self, owner: str) -> List[Dict]:
        return list(self._loader(owner) or [])

    def matching_rules(self, owner: str, email: Dict) -> List[Dict]:
        """Return enabled rules whose matchers all pass, with parsed actions."""
        matched = []
        for rule in self.load_rules(owner):
            if not rule.get("enabled", True):
                continue
            if rule_matches(rule, email):
                matched.append(rule)
        return matched

    def matching_actions(self, owner: str, email: Dict) -> List[str]:
        """Union of actions across all matching rules (deduped, ordered)."""
        actions: List[str] = []
        for rule in self.matching_rules(owner, email):
            for action in parse_actions(rule.get("actions")):
                if action not in actions:
                    actions.append(action)
        return actions


def execute_rule_actions(
    owner: str,
    email: Dict,
    actions: List[str],
    db_factory=None,
) -> List[Dict]:
    """Apply side effects for matched actions against one email.

    Currently implements `create_task` (inserts a checklist Note sourced from
    the email). Other vocabulary actions are advisory: they gate behaviour the
    existing pipelines already provide (summarize pass, auto-reply pass, event
    extractor) and are returned in the result list for callers to honour.

    Returns list of {"action": ..., "ok": bool, "detail": str}.
    """
    from core.database import SessionLocal, Note
    db = db_factory() if db_factory is not None else SessionLocal()
    results: List[Dict] = []
    try:
        subject = (email.get("subject") or "(no subject)")[:200]
        for action in actions:
            if action == "create_task":
                note = Note(
                    id=str(uuid.uuid4()),
                    owner=owner,
                    title=f"Task from email: {subject}",
                    content=(email.get("body") or email.get("snippet") or "")[:2000],
                    items=json.dumps([{"text": subject, "done": False}]),
                    note_type="checklist",
                    source="email-rule",
                    archived=False,
                    pinned=False,
                )
                db.add(note)
                db.commit()
                results.append({"action": action, "ok": True, "detail": note.id})
            else:
                results.append({
                    "action": action, "ok": True,
                    "detail": "advisory — gated by the matching built-in email pipeline",
                })
        return results
    except Exception as exc:
        db.rollback()
        logger.warning("email rule action execution failed for %s: %s", owner, exc)
        return [{"action": a, "ok": False, "detail": str(exc)} for a in actions]
    finally:
        db.close()


# Helpers shared by routes/email_rules.py ─────────────────────────────────────

def row_to_rule(row) -> Dict:
    matchers = row.matchers or "{}"
    try:
        matchers = json.loads(matchers) if isinstance(matchers, str) else matchers
    except json.JSONDecodeError:
        matchers = {}
    actions = row.actions or "[]"
    if isinstance(actions, str):
        try:
            actions = json.loads(actions)
        except json.JSONDecodeError:
            actions = []
    return {
        "id": row.id,
        "owner": row.owner,
        "name": row.name,
        "matchers": matchers,
        "actions": parse_actions(actions),
        "enabled": bool(row.enabled),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def db_rules_loader(owner: str, db_factory=None):
    """Build a rules_loader bound to the DB layer."""
    from core.database import EmailRule
    db = db_factory() if db_factory is not None else None

    def _load(owner_: str):
        nonlocal db
        from core.database import SessionLocal
        close_after = db is None
        session = db if db is not None else SessionLocal()
        try:
            rows = (
                session.query(EmailRule)
                .filter(EmailRule.owner == owner_)
                .order_by(EmailRule.created_at.desc())
                .all()
            )
            return [row_to_rule(r) for r in rows]
        finally:
            if close_after:
                session.close()

    return _load
