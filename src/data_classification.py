"""SFD §5.19 — Classification et rétention des données.

5 niveaux :
  Public    — illimitée
  Interne   — durée workspace + 90 jours
  Personnel — illimitée (droit à l'oubli)
  Sensible  — session uniquement
  Protégé   — jamais persisté

Gated behind ODYSSEUS_DATA_CLASSIFICATION kill-switch (default OFF).
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from src.app_context import app_context


logger = logging.getLogger(__name__)

# ─── Kill-switch ────────────────────────────────────────────────────────


def data_classification_enabled() -> bool:
    val = os.getenv("ODYSSEUS_DATA_CLASSIFICATION", "on").strip().lower()
    return val in {"on", "1", "true", "yes"}


# ─── Types ──────────────────────────────────────────────────────────────


class RetentionLevel(str, Enum):
    PUBLIC = "public"  # Illimitée
    INTERNAL = "internal"  # Workspace + 90 jours
    PERSONAL = "personal"  # Illimitée (droit à l'oubli)
    SENSITIVE = "sensitive"  # Session uniquement
    PROTECTED = "protected"  # Jamais persisté


@dataclass
class DataClassified:
    key: str
    level: RetentionLevel
    created_at: float = field(default_factory=time.time)
    expires_at: float | None = None
    session_id: str | None = None


# ─── Classification rules ───────────────────────────────────────────────

# Patterns qui déclenchent chaque niveau
CLASSIFICATION_PATTERNS: dict[RetentionLevel, list[str]] = {
    RetentionLevel.PUBLIC: [
        r"préférence de format",
        r"langue",
        r"skills? public",
    ],
    RetentionLevel.INTERNAL: [
        r"plan de projet",
        r"historique d.exécution",
        r"décision",
        r"workflow",
        r"configuration",
    ],
    RetentionLevel.PERSONAL: [
        r"prénom",
        r"nom",
        r"rôle",
        r"email professionnel",
        r"préférence culinaire",
        r"intérêt",
    ],
    RetentionLevel.SENSITIVE: [
        r"localisation",
        r"adresse IP",
        r"données de session",
        r"historique de navigation",
    ],
    RetentionLevel.PROTECTED: [
        r"santé",
        r"religion",
        r"orientation",
        r"ethnique",
        r"données bancaires",
        r"sécurité sociale",
        r"casier",
        r"diagnostic",
        r"thérapie",
        r"addiction",
        r"enfant",
        r"mineur",
    ],
}


# ─── Retention engine ───────────────────────────────────────────────────


class DataClassificationEngine:
    """Moteur de classification et rétention des données."""

    def __init__(self, workspace_duration_days: int = 365):
        self.workspace_duration_days = workspace_duration_days
        self.index: dict[str, DataClassified] = {}
        self._load_index()

    def classify(self, key: str, content: str, session_id: str | None = None) -> RetentionLevel:
        """Classifie une donnée et détermine son niveau de rétention."""
        content_lower = content.lower()

        # Niveau 5 (priorité max) : Protégé
        for pattern in CLASSIFICATION_PATTERNS[RetentionLevel.PROTECTED]:
            import re

            if re.search(pattern, content_lower):
                # Only the *decision* is recorded (key + level, never the
                # content). The payload is the caller's responsibility: it must
                # consult should_persist() before writing anywhere durable.
                logger.info("Classified '%s' as PROTECTED — content must not be persisted", key)
                self._record(key, RetentionLevel.PROTECTED, session_id, expires_at=0)
                return RetentionLevel.PROTECTED

        # Niveau 4 : Sensible
        for pattern in CLASSIFICATION_PATTERNS[RetentionLevel.SENSITIVE]:
            import re

            if re.search(pattern, content_lower):
                expires = time.time() + 3600  # 1 heure max
                self._record(key, RetentionLevel.SENSITIVE, session_id, expires_at=expires)
                return RetentionLevel.SENSITIVE

        # Niveau 3 : Personnel
        for pattern in CLASSIFICATION_PATTERNS[RetentionLevel.PERSONAL]:
            import re

            if re.search(pattern, content_lower):
                self._record(key, RetentionLevel.PERSONAL, session_id)
                return RetentionLevel.PERSONAL

        # Niveau 2 : Interne
        for pattern in CLASSIFICATION_PATTERNS[RetentionLevel.INTERNAL]:
            import re

            if re.search(pattern, content_lower):
                expires = time.time() + (self.workspace_duration_days + 90) * 86400
                self._record(key, RetentionLevel.INTERNAL, session_id, expires_at=expires)
                return RetentionLevel.INTERNAL

        # Niveau 1 (défaut) : Public
        self._record(key, RetentionLevel.PUBLIC, session_id)
        return RetentionLevel.PUBLIC

    def should_persist(self, key: str, content: str) -> bool:
        """Retourne False si la donnée ne doit pas être persistée."""
        level = self.classify(key, content)
        return level != RetentionLevel.PROTECTED

    def should_purge(self, key: str) -> bool:
        """Retourne True si la donnée a expiré et doit être purgée."""
        entry = self.index.get(key)
        if entry is None:
            return False
        if entry.level == RetentionLevel.PROTECTED:
            return True  # Ne devrait pas exister
        if entry.level == RetentionLevel.SENSITIVE and entry.session_id:
            # Purger si la session est terminée
            return True  # Simplifié : toujours purger après session
        if entry.expires_at and time.time() > entry.expires_at:
            return True
        return False

    def forget(self, key: str) -> bool:
        """Droit à l'oubli : supprime définitivement une donnée."""
        if key in self.index:
            del self.index[key]
            self._save_index()
            logger.info("Forgot '%s' — permanently deleted", key)
            return True
        return False

    def forget_all(self) -> int:
        """Droit à l'oubli total."""
        count = len(self.index)
        self.index.clear()
        self._save_index()
        logger.info("Forgot all %d entries", count)
        return count

    def _record(
        self, key: str, level: RetentionLevel, session_id: str | None = None, expires_at: float | None = None
    ) -> None:
        self.index[key] = DataClassified(
            key=key,
            level=level,
            session_id=session_id,
            expires_at=expires_at,
        )
        self._save_index()

    def _load_index(self) -> None:
        path = Path("data/classification_index.json")
        try:
            if path.exists():
                data = json.loads(path.read_text())
                for item in data:
                    self.index[item["key"]] = DataClassified(
                        key=item["key"],
                        level=RetentionLevel(item["level"]),
                        created_at=item.get("created_at", 0),
                        expires_at=item.get("expires_at"),
                        session_id=item.get("session_id"),
                    )
        except Exception as e:
            logger.warning("Failed to load classification index: %s", e)

    def _save_index(self) -> None:
        path = Path("data/classification_index.json")
        # The caller is the agent loop, whose blanket `except` turns any raise
        # here into "classification skipped" at DEBUG level. Without this mkdir
        # the first classify() outside a project directory raised
        # FileNotFoundError and the P17 gate silently did not exist.
        path.parent.mkdir(parents=True, exist_ok=True)
        data = [
            {
                "key": dc.key,
                "level": dc.level.value,
                "created_at": dc.created_at,
                "expires_at": dc.expires_at,
                "session_id": dc.session_id,
            }
            for dc in self.index.values()
        ]
        path.write_text(json.dumps(data, indent=2))


# ─── Singleton ───────────────────────────────────────────────────────────

app_context.caches.planning_engine: DataClassificationEngine | None = None


def get_classification_engine() -> DataClassificationEngine:
    if app_context.caches.planning_engine is None:
        app_context.caches.planning_engine = DataClassificationEngine()
    return app_context.caches.planning_engine
