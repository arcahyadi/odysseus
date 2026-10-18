"""Database Protocol — Interface unique pour l'accès base de données (MOD-6).

Ce module définit le Protocol que tous les modules doivent utiliser au lieu
d'importer core.database directement. L'implémentation concrète est dans
database_impl.py qui wrappe core.database.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Generic, Iterator, TypeVar

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from sqlalchemy.orm.query import Query
    from sqlalchemy.engine import Engine

T = TypeVar("T")


class DatabaseProtocol:
    """Interface minimale pour l'accès à la base de données.
    
    Tous les modules doivent dépendre de ce protocol, pas de core.database.
    L'implémentation concrète est DatabaseImpl (database_impl.py).
    """
    
    def get_session(self) -> "Session":
        """Retourne une nouvelle session SQLAlchemy."""
        ...
    
    def execute(self, statement: Any, params: dict | None = None) -> Any:
        """Exécute une requête SQL brute."""
        ...
    
    def query(self, model: type[T]) -> "Query[T]":
        """Retourne un Query SQLAlchemy pour le modèle donné."""
        ...
    
    def add(self, instance: Any) -> None:
        """Ajoute une instance à la session."""
        ...
    
    def commit(self) -> None:
        """Commit la transaction courante."""
        ...
    
    def rollback(self) -> None:
        """Rollback la transaction courante."""
        ...
    
    def flush(self) -> None:
        """Flush la session sans commit."""
        ...
    
    def refresh(self, instance: Any, attribute_names: list[str] | None = None) -> None:
        """Rafraîchit une instance depuis la DB."""
        ...
    
    def delete(self, instance: Any) -> None:
        """Supprime une instance."""
        ...
    
    @property
    def engine(self) -> "Engine":
        """Retourne le moteur SQLAlchemy sous-jacent."""
        ...
    
    def close(self) -> None:
        """Ferme la connexion."""
        ...
    
    def __enter__(self) -> "DatabaseProtocol":
        ...
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        ...

def _reset_caches() -> None:
    """Vide les caches de ce module. Pour l'isolation des tests (MOD-6).
    
    Ce module n'a pas de cache propre (c'est un Protocol),
    mais la fonction existe pour l'isolation des tests (MOD-6).
    """
