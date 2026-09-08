"""
routes/email_rules.py

CRUD + evaluate API for email automation rules.
Prefix: /api/email-rules
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from core.database import SessionLocal, EmailRule
from src.auth_helpers import get_current_user
from services.email_rules import row_to_rule, parse_actions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/email-rules", tags=["email-rules"])


class RuleBody(BaseModel):
    name: str = ""
    matchers: Dict = {}
    actions: List[str] = []
    enabled: bool = True


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _get_rule(rule_id: str, owner: str):
    db = SessionLocal()
    try:
        rule = db.query(EmailRule).filter_by(id=rule_id, owner=owner).first()
        return rule, db
    except Exception:
        db.close()
        raise


@router.get("")
def list_rules(request: Request):
    """Return all rules for the current owner, newest first."""
    user = get_current_user(request) or ""
    db = SessionLocal()
    try:
        rows = db.query(EmailRule).filter_by(owner=user).order_by(EmailRule.created_at.desc()).all()
        return {"rules": [row_to_rule(r) for r in rows]}
    finally:
        db.close()


@router.post("", status_code=201)
def create_rule(body: RuleBody, request: Request):
    """Create a rule."""
    user = get_current_user(request) or ""
    actions = parse_actions(body.actions)
    matchers = {k: str(v) for k, v in (body.matchers or {}).items() if v}
    now = _utcnow()
    db = SessionLocal()
    try:
        rule = EmailRule(
            id=str(uuid.uuid4()),
            owner=user,
            name=(body.name or "").strip() or "Untitled rule",
            matchers=json.dumps(matchers, ensure_ascii=False),
            actions=json.dumps(actions),
            enabled=bool(body.enabled),
            created_at=now,
            updated_at=now,
        )
        db.add(rule)
        db.commit()
        db.refresh(rule)
        return row_to_rule(rule)
    finally:
        db.close()


@router.put("/{rule_id}")
def update_rule(rule_id: str, body: RuleBody, request: Request):
    """Update a rule's matchers/actions/enabled/name."""
    user = get_current_user(request) or ""
    db = SessionLocal()
    try:
        rule = db.query(EmailRule).filter_by(id=rule_id, owner=user).first()
        if rule is None:
            raise HTTPException(404, "Rule not found")
        matchers = {k: str(v) for k, v in (body.matchers or {}).items() if v}
        rule.name = (body.name or "").strip() or rule.name
        rule.matchers = json.dumps(matchers, ensure_ascii=False)
        rule.actions = json.dumps(parse_actions(body.actions))
        rule.enabled = bool(body.enabled)
        rule.updated_at = _utcnow()
        db.commit()
        db.refresh(rule)
        return row_to_rule(rule)
    finally:
        db.close()


@router.post("/{rule_id}/toggle")
def toggle_rule(rule_id: str, request: Request):
    """Flip a rule's enabled flag."""
    user = get_current_user(request) or ""
    db = SessionLocal()
    try:
        rule = db.query(EmailRule).filter_by(id=rule_id, owner=user).first()
        if rule is None:
            raise HTTPException(404, "Rule not found")
        rule.enabled = not rule.enabled
        rule.updated_at = _utcnow()
        db.commit()
        db.refresh(rule)
        return {"id": rule.id, "enabled": bool(rule.enabled)}
    finally:
        db.close()


@router.delete("/{rule_id}")
def delete_rule(rule_id: str, request: Request):
    """Delete a rule."""
    user = get_current_user(request) or ""
    db = SessionLocal()
    try:
        rule = db.query(EmailRule).filter_by(id=rule_id, owner=user).first()
        if rule is None:
            raise HTTPException(404, "Rule not found")
        db.delete(rule)
        db.commit()
        return {"ok": True}
    finally:
        db.close()


class EvaluateBody(BaseModel):
    """An email to test against the owner's rules (no side effects)."""

    sender: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    snippet: Optional[str] = None
    folder: Optional[str] = "INBOX"
    include_actions: bool = True


@router.post("/evaluate")
def evaluate(body: EvaluateBody, request: Request):
    """Return the rules (and matching action vocabulary) for one email.

    Read-only — no tasks/notes are created here; use /execute for side effects.
    """
    from services.email_rules import db_rules_loader, RuleEngine
    user = get_current_user(request) or ""
    email = {
        "sender": body.sender,
        "subject": body.subject,
        "body": body.body or body.snippet,
        "folder": body.folder,
    }
    loader = db_rules_loader(user)
    engine = RuleEngine(rules_loader=loader)
    rules = engine.matching_rules(user, email)
    return {
        "matched": rules,
        "actions": engine.matching_actions(user, email) if body.include_actions else [],
    }


class ExecuteBody(EvaluateBody):
    """Like evaluate, but applies side effects for matched actions."""

    dry_run: bool = False


@router.post("/execute")
def execute(body: ExecuteBody, request: Request):
    """Apply side effects for matched actions against one email.

    create_task inserts a checklist Note; other actions are advisory (the
    existing built-in email pipelines honour them). dry_run skips side effects.
    """
    from services.email_rules import db_rules_loader, RuleEngine, execute_rule_actions
    user = get_current_user(request) or ""
    email = {
        "sender": body.sender,
        "subject": body.subject,
        "body": body.body or body.snippet,
        "folder": body.folder,
    }
    loader = db_rules_loader(user)
    engine = RuleEngine(rules_loader=loader)
    rules = engine.matching_rules(user, email)
    actions = engine.matching_actions(user, email)
    if body.dry_run or not actions:
        return {"matched": rules, "actions": actions, "executed": []}
    executed = execute_rule_actions(user, email, actions)
    return {"matched": rules, "actions": actions, "executed": executed}
