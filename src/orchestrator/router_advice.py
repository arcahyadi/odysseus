"""Advisory routing for the LIVE loop (M3.1) — retargeted to NATIVE roles.

`intent_gate.classify_intent` had ZERO live call-sites; this module is its first
live consumer. It classifies the user's intent and maps it to a **native role**
(`default`/`utility`/`research`/`vision`) that the native `resolve_endpoint`
already knows how to turn into a real endpoint+model+fallback chain.

WHY NOT ModelRouter: the native-capability map (`.planning/intel/INDEX.md §2`)
graded `src/llm_router.py::ModelRouter` REDUNDANT — it carries a phantom model
catalog (`model-routing.json`: deepseek-v4-pro, kimi-k2.6, glm-5.2…) with no
dispatch call-site and duplicates native role-resolution. This module therefore
suggests a native ROLE, never a phantom model id.

SAFETY / SCOPE: advisory only. OFF by default (`ODYSSEUS_MODEL_ROUTER`); when ON
it only logs the suggested role. It NEVER overrides the user's chosen model.
"""

from __future__ import annotations

import logging
import os

from src.intent_gate import classify_intent

logger = logging.getLogger(__name__)

# intent_gate category → native setting-prefix role understood by resolve_endpoint.
# Native roles: default / utility / research / vision (see intel domain 01 §1.4).
_INTENT_ROLE_MAP = {
    "quick": "utility",
    "utility": "utility",
    "deep": "research",
    "code": "default",
    "creative": "default",
    "vision": "vision",
}
_DEFAULT_ROLE = "default"


def router_enabled() -> bool:
    """OFF unless ODYSSEUS_MODEL_ROUTER is set to a truthy value."""
    val = os.getenv("ODYSSEUS_MODEL_ROUTER", "on").strip().lower()
    return val in {"on", "1", "true", "yes"}


def intent_to_role(intent: str) -> str:
    """Map an intent_gate category to a NATIVE role prefix (never a model id)."""
    return _INTENT_ROLE_MAP.get(intent, _DEFAULT_ROLE)


def advise(user_text: str, stage: str | None = None) -> dict:
    """Classify intent and suggest a native role (advisory).

    Returns {"intent": str, "stage": str|None, "suggested_role": str}.
    Never raises: any failure falls back to the "default" role.
    """
    try:
        intent = classify_intent(user_text or "")
    except Exception as exc:  # classification must never break chat
        logger.debug("[router-advice] classify_intent failed: %s", exc)
        intent = "utility"

    return {
        "intent": intent,
        "stage": stage,
        "suggested_role": intent_to_role(intent),
    }
