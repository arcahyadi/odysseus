"""Database Implementation — Implémentation concrète du DatabaseProtocol (MOD-6).

Ce module wrappe core.database et expose l'API via DatabaseProtocol.
C'est le SEUL module autorisé à importer core.database directement.
"""

from __future__ import annotations

import contextlib
from typing import Any, Iterator, TypeVar

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker, Query

from src.database_protocol import DatabaseProtocol
from src.app_context import app_context

# Import core.database ICI SEULEMENT - c'est le point unique d'accès
from core.database import (
    SessionLocal as CoreSessionLocal,
    engine as core_engine,
    Base,
    ModelEndpoint,
    Webhook,
    Session as CoreSession,
)

T = TypeVar("T")


class DatabaseImpl(DatabaseProtocol):
    """Implémentation concrète du DatabaseProtocol wrappeant core.database.
    
    Ce module est le SEUL autorisé à importer core.database directement.
    Tous les autres modules doivent passer par DatabaseProtocol via AppContext.
    """
    
    def __init__(self):
        self._session_factory = CoreSessionLocal
        self._engine = core_engine
    
    def get_session(self) -> Any:
        """Retourne une nouvelle session SQLAlchemy."""
        return self._session_factory()
    
    @contextlib.contextmanager
    def session_scope(self) -> Iterator[Any]:
        """Context manager pour une session avec commit/rollback auto."""
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def execute(self, statement: Any, params: dict | None = None) -> Any:
        """Exécute une requête SQL brute."""
        with self.session_scope() as session:
            if params:
                return session.execute(text(statement), params)
            return session.execute(text(statement))
    
    def query(self, model: type) -> Any:
        """Retourne un Query SQLAlchemy pour le modèle donné."""
        session = self.get_session()
        return session.query(model)
    
    def add(self, instance: Any) -> None:
        """Ajoute une instance à la session."""
        session = self.get_session()
        session.add(instance)
    
    def commit(self) -> None:
        """Commit la transaction courante."""
        session = self.get_session()
        session.commit()
    
    def rollback(self) -> None:
        """Rollback la transaction courante."""
        session = self.get_session()
        session.rollback()
    
    def flush(self) -> None:
        """Flush la session sans commit."""
        session = self.get_session()
        session.flush()
    
    def refresh(self, instance: Any, attribute_names: list[str] | None = None) -> None:
        """Rafraîchit une instance depuis la DB."""
        session = self.get_session()
        session.refresh(instance, attribute_names=attribute_names)
    
    def delete(self, instance: Any) -> None:
        """Supprime une instance."""
        session = self.get_session()
        session.delete(instance)
    
    @property
    def engine(self) -> Any:
        """Retourne le moteur SQLAlchemy sous-jacent."""
        return self._engine
    
    def close(self) -> None:
        """Ferme la connexion."""
        self._engine.dispose()
    
    def __enter__(self) -> "DatabaseImpl":
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()
    
    # ---- Méthodes de compatibilité pour migration progressive ----
    
    @property
    def SessionLocal(self):
        """Compatibilité : accès direct au SessionLocal."""
        return CoreSessionLocal
    
    @property
    def Session(self) -> type:
        """Compatibilité : Session class."""
        return CoreSession
    
    # Modèles ré-exportés pour compatibilité
    ModelEndpoint = ModelEndpoint
    Webhook = Webhook
    Session = CoreSession


# Instance singleton pour accès direct (sera migrée vers AppContext)
_database_impl: DatabaseImpl | None = None


def get_database() -> DatabaseImpl:
    """Retourne l'instance singleton de DatabaseImpl."""
    global _database_impl
    if _database_impl is None:
        _database_impl = DatabaseImpl()
    return _database_impl


def init_database() -> DatabaseImpl:
    """Initialise la base de données (création des tables)."""
    Base.metadata.create_all(bind=core_engine)
    return get_database()

def _reset_caches() -> None:
    """Vide les caches de ce module. Pour l'isolation des tests (MOD-6).
    
    Vide l'instance singleton.
    """
    global _database_impl
    _database_impl = None
