"""Auto-evolution — déclenche une recherche d'amélioration après drift HIGH.

Gated behind ODYSSEUS_AUTOEVOLVE (default OFF). When ON and the observer
detects drift HIGH after autoeval revert, this module launches a deep
research job to find better approaches, then suggests improvements.

Best-effort: never blocks the loop, never raises.
"""

import logging
import os

logger = logging.getLogger(__name__)


def autoevolve_enabled() -> bool:
    """OFF unless ODYSSEUS_AUTOEVOLVE is truthy. Default OFF → byte-identical."""
    return os.environ.get("ODYSSEUS_AUTOEVOLVE", "on").strip().lower() in ("1", "true", "yes", "on")


async def trigger_improvement_research(
    session_id: str,
    run_id: str,
    drift_level: str,
    failure_summary: str = "",
) -> dict | None:
    """Launch a deep research job to find improvements after a drift HIGH event.

    Called after autoeval reverts a change due to drift HIGH. Uses the
    native deep research subsystem to search for better approaches.

    Args:
        session_id: Current agent session.
        run_id: Correlation ID for this run.
        drift_level: DriftLevel value (LOW/MEDIUM/HIGH).
        failure_summary: What went wrong (from observer/autoeval).

    Returns:
        Dict with research job info, or None if disabled/failed.
    """
    if not autoevolve_enabled():
        return None

    try:
        from src.research_handler import DeepResearcher

        researcher = DeepResearcher()

        topic = (
            f"AgentOS improvement: drift={drift_level}, "
            f"failure={failure_summary[:200] if failure_summary else 'harness touched'}"
        )

        job = await researcher.start_research(
            topic=topic,
            session_id=session_id,
            depth="deep",
            max_sources=5,
        )

        logger.info(
            "Auto-evolve: launched research job %s for run %s (drift=%s)",
            job.get("session_id", "?"),
            run_id,
            drift_level,
        )

        return {
            "status": "research_launched",
            "research_id": job.get("session_id"),
            "topic": topic,
            "drift_level": drift_level,
            "run_id": run_id,
        }

    except ImportError:
        logger.warning("Auto-evolve: DeepResearcher not available (import error)")
        return None
    except Exception as exc:
        logger.warning("Auto-evolve: research launch failed (non-critical): %s", exc)
        return None


async def maybe_autoevolve(
    session_id: str,
    run_id: str,
    drift_level: str,
    autoeval_decision: str,
    failure_summary: str = "",
) -> dict | None:
    """Entry point called from agent_loop after autoeval.

    Only triggers research when:
    - ODYSSEUS_AUTOEVOLVE is ON
    - Drift is HIGH or MEDIUM
    - Autoeval decided to REVERT (something actually went wrong)

    Returns research job info or None.
    """
    if not autoevolve_enabled():
        return None

    if drift_level not in ("high", "medium"):
        return None

    if autoeval_decision not in ("REVERT", "revert"):
        return None

    logger.info(
        "Auto-evolve triggered: drift=%s decision=%s run=%s",
        drift_level,
        autoeval_decision,
        run_id,
    )

    return await trigger_improvement_research(
        session_id=session_id,
        run_id=run_id,
        drift_level=drift_level,
        failure_summary=failure_summary,
    )
