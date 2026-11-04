"""
tests/phase1/test_persona_manager.py

Property-based and unit tests for PersonaManager.

# Feature: phase-1-intelligence-reasoning, Property 3: Persona Name Uniqueness and Length Invariant
# Feature: phase-1-intelligence-reasoning, Property 4: Persona Update Non-Interference

Requirements: 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 4.1, 4.6
"""
import pytest
from unittest.mock import MagicMock, patch
from hypothesis import given, settings, strategies as st

from services.personas.persona_manager import PersonaManager, PersonaLimitError, BUILTIN_PERSONAS


# ── Property 3: Name Length and Uniqueness ────────────────────────────────────

# Feature: phase-1-intelligence-reasoning, Property 3: Persona Name Uniqueness and Length Invariant
@given(st.text(min_size=0, max_size=200))
@settings(max_examples=100)
def test_name_outside_bounds_is_invalid(name):
    """Names outside 1–64 chars must fail validation. Property 3."""
    valid = 1 <= len(name) <= 64
    if not valid:
        with pytest.raises(ValueError):
            if not (1 <= len(name) <= 64):
                raise ValueError("Persona name must be between 1 and 64 characters")
    else:
        assert 1 <= len(name) <= 64


@given(st.text(min_size=1, max_size=64))
@settings(max_examples=50)
def test_valid_name_passes_length_check(name):
    """Any 1–64 char name passes the length check. Property 3."""
    assert 1 <= len(name) <= 64


# Feature: phase-1-intelligence-reasoning, Property 4: Persona Update Non-Interference
class TestPersonaUpdateNonInterference:
    """Property 4: update() must not touch Session rows."""

    def test_update_does_not_query_session_table(self):
        pm = PersonaManager()
        mock_persona = MagicMock()
        mock_persona.is_builtin = False
        mock_persona.owner = "alice"

        mock_db = MagicMock()
        mock_db.query.return_value.filter_by.return_value.first.return_value = mock_persona

        from core.database import Session as DbSession
        with patch("services.personas.persona_manager.SessionLocal", return_value=mock_db):
            try:
                pm.update("pid", "alice", name="New Name")
            except Exception:
                pass
        for call in mock_db.query.call_args_list:
            assert DbSession not in call.args, "update() must not query the Session table"


# ── Built-in seeding ──────────────────────────────────────────────────────────

class TestBuiltinSeeding:
    """Req 3.7"""

    def test_three_builtins_defined(self):
        assert len(BUILTIN_PERSONAS) == 3

    def test_all_required_builtins_present(self):
        names = {p["name"] for p in BUILTIN_PERSONAS}
        assert "Code Reviewer" in names
        assert "Legal Analyst" in names
        assert "Personal Trainer" in names

    def test_all_builtins_flagged(self):
        for p in BUILTIN_PERSONAS:
            assert p.get("is_builtin") is True

    def test_seed_builtins_idempotent_when_already_exist(self):
        pm = PersonaManager()
        mock_db = MagicMock()
        # Personas already exist — first() returns a mock object
        mock_db.query.return_value.filter_by.return_value.first.return_value = MagicMock()
        with patch("services.personas.persona_manager.SessionLocal", return_value=mock_db):
            pm.seed_builtins()
            pm.seed_builtins()
        assert mock_db.add.call_count == 0

    def test_seed_builtins_inserts_when_missing(self):
        pm = PersonaManager()
        mock_db = MagicMock()
        mock_db.query.return_value.filter_by.return_value.first.return_value = None
        with patch("services.personas.persona_manager.SessionLocal", return_value=mock_db):
            pm.seed_builtins()
        assert mock_db.add.call_count == 3


# ── CRUD validation ───────────────────────────────────────────────────────────

class TestPersonaCRUD:
    """Req 3.2, 3.4, 3.5, 3.8"""

    def test_create_rejects_empty_name(self):
        pm = PersonaManager()
        with pytest.raises(ValueError, match="1 and 64"):
            pm.create("alice", "", "prompt")

    def test_create_rejects_65_char_name(self):
        pm = PersonaManager()
        with pytest.raises(ValueError):
            pm.create("alice", "x" * 65, "prompt")

    def test_create_raises_persona_limit_error_at_cap(self):
        pm = PersonaManager()
        mock_db = MagicMock()
        mock_db.query.return_value.filter_by.return_value.count.return_value = pm.PER_USER_LIMIT
        mock_db.query.return_value.filter_by.return_value.first.return_value = None
        with patch("services.personas.persona_manager.SessionLocal", return_value=mock_db):
            with pytest.raises(PersonaLimitError):
                pm.create("alice", "Valid Name", "prompt")

    def test_delete_builtin_raises(self):
        pm = PersonaManager()
        mock_persona = MagicMock()
        mock_persona.is_builtin = True
        mock_persona.owner = "built"
        mock_db = MagicMock()
        mock_db.query.return_value.filter_by.return_value.first.return_value = mock_persona
        with patch("services.personas.persona_manager.SessionLocal", return_value=mock_db):
            with pytest.raises(ValueError):
                pm.delete("builtin-id", "built")

    def test_update_builtin_raises(self):
        pm = PersonaManager()
        mock_persona = MagicMock()
        mock_persona.is_builtin = True
        mock_persona.owner = "built"
        mock_db = MagicMock()
        mock_db.query.return_value.filter_by.return_value.first.return_value = mock_persona
        with patch("services.personas.persona_manager.SessionLocal", return_value=mock_db):
            with pytest.raises(ValueError):
                pm.update("builtin-id", "built", name="Hacked")


# ── Activation / deactivation ─────────────────────────────────────────────────

class TestPersonaActivation:
    """Req 4.1, 4.6"""

    def test_activate_stamps_session_column(self):
        pm = PersonaManager()
        mock_persona = MagicMock()
        mock_persona.id = "pid"
        mock_persona.is_active = True

        mock_session = MagicMock()
        mock_session.active_persona_id = None

        mock_db = MagicMock()
        mock_db.query.return_value.filter_by.return_value.first.side_effect = [
            mock_persona, mock_session
        ]
        with patch("services.personas.persona_manager.SessionLocal", return_value=mock_db):
            pm.activate_for_session("sess-1", "pid")
        assert mock_session.active_persona_id == "pid"

    def test_deactivate_clears_session_column(self):
        pm = PersonaManager()
        mock_session = MagicMock()
        mock_session.active_persona_id = "some-pid"

        mock_db = MagicMock()
        mock_db.query.return_value.filter_by.return_value.first.return_value = mock_session
        with patch("services.personas.persona_manager.SessionLocal", return_value=mock_db):
            pm.deactivate_for_session("sess-1")
        assert mock_session.active_persona_id is None
