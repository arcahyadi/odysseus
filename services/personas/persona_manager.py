import json
import logging
import os
import uuid
from typing import Optional

from core.database import Persona, Session as DbSession, SessionLocal, utcnow_naive

logger = logging.getLogger(__name__)

BUILTIN_PERSONAS = [
    {
        "id": "builtin-code-reviewer",
        "name": "Code Reviewer",
        "system_prompt": (
            "You are an expert code reviewer. Analyse the provided code for correctness, "
            "security vulnerabilities, performance issues, and style. Be specific: reference "
            "exact line numbers, explain the problem clearly, and suggest a concrete fix for "
            "each issue you find."
        ),
        "allowed_tools": '["read_file", "run_tests"]',
        "memory_scope": "session",
        "is_builtin": True,
    },
    {
        "id": "builtin-legal-analyst",
        "name": "Legal Analyst",
        "system_prompt": (
            "You are a careful legal analyst. Review the provided document and identify: "
            "key obligations, risks, important deadlines, non-standard clauses, and ambiguous "
            "language. Structure your response clearly. Always note that your analysis is "
            "informational and does not constitute legal advice."
        ),
        "allowed_tools": '[]',
        "memory_scope": "session",
        "is_builtin": True,
    },
    {
        "id": "builtin-personal-trainer",
        "name": "Personal Trainer",
        "system_prompt": (
            "You are an encouraging and knowledgeable personal fitness coach. Create personalised "
            "workout plans, adapt them to the user's available time, equipment, and goals. Track "
            "progress across sessions and provide clear motivation. Always recommend consulting a "
            "medical professional before starting a new exercise program."
        ),
        "allowed_tools": '[]',
        "memory_scope": "global",
        "is_builtin": True,
    },
]


class PersonaLimitError(Exception):
    """Raised when a user has reached the maximum allowed persona count."""


class PersonaManager:
    PER_USER_LIMIT = int(os.getenv("PERSONA_PER_USER_LIMIT", "50"))

    def seed_builtins(self) -> None:
        """Idempotent upsert of built-in personas at startup. Requirements: 3.7"""
        db = SessionLocal()
        try:
            for p in BUILTIN_PERSONAS:
                existing = db.query(Persona).filter_by(id=p["id"]).first()
                if not existing:
                    db.add(Persona(**p))
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("Failed to seed built-in personas")
            raise
        finally:
            db.close()

    def create(self, owner: str, name: str, system_prompt: str, **kwargs) -> Persona:
        """
        Validate and persist a new Persona. Requirements: 3.1, 3.2, 3.5, 3.8
        Raises PersonaLimitError if user has >= PER_USER_LIMIT active personas.
        Raises ValueError if name is not 1-64 chars or already exists for this owner.
        """
        if not (1 <= len(name) <= 64):
            raise ValueError("Persona name must be between 1 and 64 characters")

        db = SessionLocal()
        try:
            # Enforce per-user limit (requirement 3.8)
            count = db.query(Persona).filter_by(owner=owner, is_active=True).count()
            if count >= self.PER_USER_LIMIT:
                raise PersonaLimitError(
                    f"Per-user persona limit of {self.PER_USER_LIMIT} reached. "
                    "Delete an existing persona before creating a new one."
                )

            # Enforce name uniqueness per owner (requirement 3.5)
            duplicate = (
                db.query(Persona)
                .filter_by(owner=owner, name=name, is_active=True)
                .first()
            )
            if duplicate:
                raise ValueError(f"A persona named '{name}' already exists for this user")

            persona = Persona(
                id=str(uuid.uuid4()),
                owner=owner,
                name=name,
                system_prompt=system_prompt,
                is_builtin=False,
                is_active=True,
                **kwargs,
            )
            db.add(persona)
            db.commit()
            db.refresh(persona)
            return persona
        except (PersonaLimitError, ValueError):
            db.rollback()
            raise
        except Exception:
            db.rollback()
            logger.exception("Failed to create persona for owner=%s", owner)
            raise
        finally:
            db.close()

    def update(self, persona_id: str, owner: str, **kwargs) -> Persona:
        """
        Update mutable fields of a user-owned Persona. Requirements: 3.3
        Raises KeyError if persona not found or not owned by owner.
        Raises ValueError if persona is a built-in.
        Does NOT touch any Session.active_persona_id references.
        """
        db = SessionLocal()
        try:
            persona = db.query(Persona).filter_by(id=persona_id).first()
            if persona is None or persona.owner != owner:
                raise KeyError(f"Persona '{persona_id}' not found or not owned by user")
            if persona.is_builtin:
                raise ValueError("Built-in personas cannot be modified")

            allowed_fields = {
                "name", "system_prompt", "allowed_tools",
                "memory_scope", "model_ref", "endpoint_url", "sort_order",
            }
            for field, value in kwargs.items():
                if field in allowed_fields:
                    setattr(persona, field, value)

            persona.updated_at = utcnow_naive()
            db.commit()
            db.refresh(persona)
            return persona
        except (KeyError, ValueError):
            db.rollback()
            raise
        except Exception:
            db.rollback()
            logger.exception("Failed to update persona id=%s", persona_id)
            raise
        finally:
            db.close()

    def delete(self, persona_id: str, owner: str) -> bool:
        """
        Soft-delete: set is_active=False. Requirements: 3.4
        Raises ValueError if built-in.
        Raises KeyError if not found or not owned by owner.
        """
        db = SessionLocal()
        try:
            persona = db.query(Persona).filter_by(id=persona_id).first()
            if persona is None or persona.owner != owner:
                raise KeyError(f"Persona '{persona_id}' not found or not owned by user")
            if persona.is_builtin:
                raise ValueError("Built-in personas cannot be deleted")

            persona.is_active = False
            persona.updated_at = utcnow_naive()
            db.commit()
            return True
        except (KeyError, ValueError):
            db.rollback()
            raise
        except Exception:
            db.rollback()
            logger.exception("Failed to delete persona id=%s", persona_id)
            raise
        finally:
            db.close()

    def list_for_user(self, owner: str) -> list:
        """
        Returns active user-owned personas PLUS all built-ins, sorted alpha by name.
        Requirements: 3.6, 3.7
        """
        db = SessionLocal()
        try:
            # Active personas belonging to the user
            user_personas = (
                db.query(Persona)
                .filter_by(owner=owner, is_active=True)
                .all()
            )
            # All built-in personas (regardless of is_active — builtins are always shown)
            builtin_personas = (
                db.query(Persona)
                .filter_by(is_builtin=True)
                .all()
            )
            combined = {p.id: p for p in builtin_personas}
            for p in user_personas:
                combined[p.id] = p
            return sorted(combined.values(), key=lambda p: p.name.lower())
        finally:
            db.close()

    def get(self, persona_id: str, owner: Optional[str] = None) -> Optional[Persona]:
        """
        Returns Persona by id.
        If owner is given, only return if owned by owner OR is built-in.
        """
        db = SessionLocal()
        try:
            persona = db.query(Persona).filter_by(id=persona_id).first()
            if persona is None:
                return None
            if owner is not None and not persona.is_builtin and persona.owner != owner:
                return None
            return persona
        finally:
            db.close()

    def activate_for_session(self, session_id: str, persona_id: str) -> Persona:
        """
        Stamp Session.active_persona_id = persona_id.
        Requirements: 4.1, 4.5
        Raises KeyError if persona not found/inactive.
        """
        db = SessionLocal()
        try:
            persona = db.query(Persona).filter_by(id=persona_id, is_active=True).first()
            if persona is None:
                raise KeyError(f"Persona '{persona_id}' not found or inactive")

            session = db.query(DbSession).filter_by(id=session_id).first()
            if session is None:
                raise KeyError(f"Session '{session_id}' not found")

            session.active_persona_id = persona_id
            db.commit()
            db.refresh(persona)
            return persona
        except KeyError:
            db.rollback()
            raise
        except Exception:
            db.rollback()
            logger.exception(
                "Failed to activate persona id=%s for session id=%s", persona_id, session_id
            )
            raise
        finally:
            db.close()

    def deactivate_for_session(self, session_id: str) -> bool:
        """
        Set Session.active_persona_id = NULL.
        Requirements: 4.6
        """
        db = SessionLocal()
        try:
            session = db.query(DbSession).filter_by(id=session_id).first()
            if session is None:
                return False
            session.active_persona_id = None
            db.commit()
            return True
        except Exception:
            db.rollback()
            logger.exception("Failed to deactivate persona for session id=%s", session_id)
            raise
        finally:
            db.close()

    def get_active_persona(self, session_id: str) -> Optional[Persona]:
        """Return the active Persona for a session, or None."""
        db = SessionLocal()
        try:
            session = db.query(DbSession).filter_by(id=session_id).first()
            if session is None or not session.active_persona_id:
                return None
            return db.query(Persona).filter_by(
                id=session.active_persona_id, is_active=True
            ).first()
        finally:
            db.close()

    def effective_tools_for_session(
        self, session_id: str, base_tools: Optional[list]
    ) -> Optional[list]:
        """
        Return intersection of base_tools and persona's allowed_tools JSON list.
        Returns base_tools unchanged if no persona active or allowed_tools is None.
        Requirements: 4.2, 13.6
        """
        persona = self.get_active_persona(session_id)
        if persona is None:
            return base_tools

        if persona.allowed_tools is None:
            return base_tools

        try:
            allowed_set = set(json.loads(persona.allowed_tools))
        except (json.JSONDecodeError, TypeError):
            logger.warning(
                "Persona id=%s has invalid allowed_tools JSON; treating as no restriction",
                persona.id,
            )
            return base_tools

        if base_tools is None:
            return None

        return [t for t in base_tools if t in allowed_set]


# Module-level singleton
persona_manager = PersonaManager()
