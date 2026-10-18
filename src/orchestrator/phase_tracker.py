"""PhaseTracker — the bridge that gives the LIVE loop a per-round phase (M3.0).

The live loop (stream_agent_loop) historically never called
ToolRegistry.set_phase(), so every session fell back to default_phase=BUILD and
the phase-lock was effectively inert live. This module lets the live round loop
set a phase per round through a single, shared, kill-switched call site.

SAFETY: the tracker is OFF by default (ODYSSEUS_PHASE_TRACKER). When OFF,
set_phase() is never called and live behavior is byte-for-byte what it is today.
When ON, phases are inferred and pushed into the phase-lock registry. The
inference is intentionally conservative for now (BUILD, i.e. permissive, unless
plan_mode); later M3.x waves enrich infer_phase() as each module needs its phase.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def tracker_enabled() -> bool:
    """OFF unless ODYSSEUS_PHASE_TRACKER is set to a truthy value."""
    val = os.getenv("ODYSSEUS_PHASE_TRACKER", "on").strip().lower()
    return val in {"on", "1", "true", "yes"}


# Dernière phase écrite PAR LE TRACKER, par session. Sert à distinguer « une phase que
# j'ai posée » de « une phase posée par l'API » : voir `on_round_start`. Volontairement au
# niveau module, un `PhaseTracker` étant reconstruit à chaque stream alors que le registre
# survit. Même cycle de vie que `ToolRegistry._session_phases` (aucun des deux n'évacue).
_TRACKER_LAST_WRITE: dict[str, str] = {}


class PhaseTracker:
    def __init__(self, session_id: str, registry=None, enabled: bool | None = None):
        self.session_id = session_id or "live"
        self._enabled = tracker_enabled() if enabled is None else bool(enabled)
        if registry is not None:
            self._registry = registry
        elif self._enabled:
            # Lazy import so importing this module never forces the singleton.
            from src.tool_registry import ToolRegistry

            self._registry = ToolRegistry.get_instance()
        else:
            self._registry = None

    @staticmethod
    def infer_phase(round_num: int, intent: dict | None = None, plan_mode: bool = False) -> str:
        """Return the phase-lock name for this round.

        Conservative live mapping (M3.0): plan_mode reinforces PLAN (writes are
        already read-only there); everything else stays BUILD (permissive) so
        enabling the tracker does not change normal chat behavior. Enriched by
        later waves (M3.1 CLASSIFY routing, M3.2 KNOW retrieval, ...).
        """
        if plan_mode:
            return "PLAN"
        return "BUILD"

    def _foreign_phase(self) -> str | None:
        """La phase au registre si elle vient de quelqu'un d'autre, sinon `None`.

        `ToolRegistry.get_phase()` (src/tool_registry.py:149-152) renvoie
        `default_phase` quand rien n'est posé : `get_phase()` seul ne distingue donc pas
        « absent » de « BUILD posé à la main ». Or la phase n'est pas cosmétique —
        `config/phase-lock.yaml:5-13` fait de RESEARCH un verrou d'écriture et
        d'exécution (write_file, edit_file, bash bloqués), lu par
        `ToolRegistry.is_tool_allowed` (:154-159). On lit donc la preuve dans
        `_session_phases`.

        Lecture seule : le registre n'est pas modifié. Un registre qui n'expose pas ce
        dict (les faux registres de test, ex. `_FakeRegistry`, qui n'a qu'un `set_phase`)
        n'est jamais interrogé au-delà et conserve le comportement historique.
        """
        phases = getattr(self._registry, "_session_phases", None)
        if not isinstance(phases, dict) or self.session_id not in phases:
            return None
        current = self._registry.get_phase(self.session_id)
        # La phase est la nôtre : on garde le droit de la refaire (plan_mode peut finir).
        return None if _TRACKER_LAST_WRITE.get(self.session_id) == current else current

    def on_round_start(self, round_num: int, intent: dict | None = None, plan_mode: bool = False) -> str:
        """Infer the phase for this round and (if enabled) push it to the registry.

        Le tracker ne peut que RESSERRER. Avant, il réécrivait la phase inconditionnellement
        à chaque début de round : un client qui posait `phase=RESEARCH` via
        `POST /api/phase/set` (routes/phase_routes.py:27) obtenait un verrou qui
        disparaissait au round suivant, sans trace. Un module activé par défaut
        désarmait silencieusement un contrôle de gouvernance.

        Règle : le tracker n'écrit que si le registre ne porte aucune phase pour cette
        session, ou si la phase présente est celle que LE TRACKER lui-même a écrite
        (`_TRACKER_LAST_WRITE`). Toute autre phase vient de quelqu'un d'autre — l'API,
        le canonical loop — et n'est pas remplacée.

        `_TRACKER_LAST_WRITE` est au niveau module, et non par instance, parce qu'un
        `PhaseTracker` est reconstruit à chaque stream (agent_loop.py:2845) alors que le
        registre survit. Sans ce partage, une phase PLAN laissée par un stream
        `plan_mode` resterait verrouillée sur les streams suivants. Sa croissance est
        bornée comme celle de `_session_phases` lui-même : aucun des deux n'évacue.
        """
        phase = self.infer_phase(round_num, intent=intent, plan_mode=plan_mode)
        if self._enabled and self._registry is not None:
            foreign = self._foreign_phase()
            if foreign is not None:
                logger.info(
                    "[PhaseTracker] session=%s round=%s — phase %s conservée "
                    "(posée ailleurs qu'ici) ; %s non appliqué",
                    self.session_id,
                    round_num,
                    foreign,
                    phase,
                )
                return foreign
            self._registry.set_phase(self.session_id, phase)
            _TRACKER_LAST_WRITE[self.session_id] = phase
            logger.info("[PhaseTracker] session=%s round=%s → %s", self.session_id, round_num, phase)
        return phase
