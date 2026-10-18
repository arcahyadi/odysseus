"""
AgentOS ZenRouter — Routing intelligent vers OpenCode Zen API.

Architecture (ANALYSE-PROFONDE §5.2) :
  1. Heuristic classifier → tier (strong / standard / fast)
  2. model-routing.json   → model_id + provider
  3. OpenCode Zen API     → réponse LLM réelle
  4. Fallback chain       → si Zen échoue

Utilisé par :
  - stream_llm_with_fallback() via inject_zen_candidate()
  - /api/route endpoint direct
  - agent_loop.py via route_intent()
"""

import json
import logging
import os
import time
from pathlib import Path

import httpx
from src.app_context import app_context


logger = logging.getLogger(__name__)

_ROUTING_CONFIG_PATH = Path(__file__).parent.parent / "model-routing.json"
app_context.caches.routing_config: dict | None = None
app_context.caches.routing_config_mtime: float = 0.0

# Last-resort model id when a config tier omits `model_id`. Must be a CONFIRMED
# catalog id (model-routing.json, tested on /zen/go/v1) — never a phantom like
# the old `deepseek-v4-flash-free`, which would be POSTed to the Zen API and
# 400 on an unknown model.
_DEFAULT_ZEN_MODEL = "deepseek-v4-flash"

# Blacklist temporaire : zen_model -> timestamp d'expiration
_zen_blacklist: dict[str, float] = {}
_zen_fail_counts: dict[str, int] = {}


def _load_routing_config() -> dict:
    """Charge model-routing.json, rechargé si modifié sur disque."""
    try:
        mtime = _ROUTING_CONFIG_PATH.stat().st_mtime
        if app_context.caches.routing_config is None or mtime > app_context.caches.routing_config_mtime:
            with open(_ROUTING_CONFIG_PATH, encoding="utf-8") as f:
                app_context.caches.routing_config = json.load(f)
            app_context.caches.routing_config_mtime = mtime
    except Exception as e:
        logger.warning(f"[ZenRouter] Cannot load model-routing.json: {e}")
        app_context.caches.routing_config = {}
    return app_context.caches.routing_config or {}


def _resolve_zen_endpoint_row():
    """Best-effort: resolve the OpenCode Zen provider from a native ModelEndpoint
    row so the DB is the single source of truth for the base URL + key when an
    admin has registered one. Returns (base_url, api_key) or None.

    Any failure (no DB, no matching row, import error) returns None → callers
    fall back to the JSON config + env, so the live chat path is byte-identical
    when no Zen endpoint is registered.
    """
    try:
        from core.database import ModelEndpoint, SessionLocal
        from src.endpoint_resolver import resolve_endpoint_runtime
    except Exception:
        return None
    try:
        db = SessionLocal()
        try:
            for ep in db.query(ModelEndpoint).all():
                base = (getattr(ep, "base_url", "") or "").lower()
                if "opencode.ai" not in base:
                    continue
                url, key = resolve_endpoint_runtime(ep)
                if url and key:
                    return url, key
        finally:
            db.close()
    except Exception:
        return None
    return None


def _zen_provider_conn(zen_cfg: dict):
    """(base_url, api_key, from_endpoint). Prefers a native ModelEndpoint row
    (single source of truth); falls back to model-routing.json + env. The third
    element tells callers whether the conn came from a registered endpoint, so
    per-candidate enablement can bypass the JSON `enabled` flag."""
    row = _resolve_zen_endpoint_row()
    if row:
        return row[0], row[1], True
    base_url = zen_cfg.get("base_url", "https://opencode.ai/zen/v1/chat/completions")
    api_key = os.getenv(zen_cfg.get("api_key_env", "OPENCODE_API_KEY"), "")
    return base_url, api_key, False


_ZEN_ENDPOINT_CACHE = {"present": None, "ts": 0.0}
_ZEN_ENDPOINT_TTL = 30.0


def _reset_zen_endpoint_cache() -> None:
    _ZEN_ENDPOINT_CACHE["present"] = None
    _ZEN_ENDPOINT_CACHE["ts"] = 0.0


def _reset_caches() -> None:
    """Vide les caches de ce module. Pour l'isolation des tests (MOD-3)."""
    _reset_zen_endpoint_cache()

def zen_endpoint_registered() -> bool:
    """Cached: is a native opencode.ai ModelEndpoint registered? Used by the
    live gate so a stream call does not hit the DB every time. Best-effort —
    any resolution failure caches False."""
    now = time.time()
    cached = _ZEN_ENDPOINT_CACHE["present"]
    if cached is not None and (now - _ZEN_ENDPOINT_CACHE["ts"]) < _ZEN_ENDPOINT_TTL:
        return cached
    present = _resolve_zen_endpoint_row() is not None
    _ZEN_ENDPOINT_CACHE["present"] = present
    _ZEN_ENDPOINT_CACHE["ts"] = now
    return present


def zen_injection_enabled() -> bool:
    """Should the live path inject Zen candidates? Env key = today's behavior
    (unchanged). A registered endpoint only enables Zen when the default-OFF
    kill-switch ODYSSEUS_ZEN_FROM_ENDPOINT=1 is set — so the live chat path is
    byte-identical by default."""
    if os.getenv("OPENCODE_API_KEY"):
        return True
    if os.getenv("ODYSSEUS_ZEN_FROM_ENDPOINT") == "1" and zen_endpoint_registered():
        return True
    return False


def classify_complexity(prompt: str) -> tuple[str, float]:
    """
    Heuristic classifier (OmO pattern) → (tier, score).
    Tiers: 'strong' | 'standard' | 'fast'
    Score: 0.0 – 1.0
    """
    cfg = _load_routing_config()
    h = cfg.get("heuristic", {})
    strong_signals = h.get("strong_signals", [])
    weak_signals = h.get("weak_signals", [])
    wc_thresholds = h.get("word_count_thresholds", {"weak_max": 8, "strong_min": 40})
    score_thresholds = h.get("score_thresholds", {"strong": 0.6, "standard": 0.35})

    text = prompt.lower()
    words = text.split()
    word_count = len(words)

    # Signaux forts / faibles
    strong_hits = sum(1 for s in strong_signals if s in text)
    weak_hits = sum(1 for s in weak_signals if s in text)

    score = 0.5  # neutre

    # Mots courts → faible
    if word_count <= wc_thresholds.get("weak_max", 8):
        score -= 0.2

    # Mots nombreux → fort
    if word_count >= wc_thresholds.get("strong_min", 40):
        score += 0.15

    score += strong_hits * 0.12
    score -= weak_hits * 0.1
    score = max(0.0, min(1.0, score))

    if score >= score_thresholds.get("strong", 0.6):
        return "strong", score
    elif score >= score_thresholds.get("standard", 0.35):
        return "standard", score
    else:
        return "fast", score


def get_zen_candidate(tier: str) -> tuple[str, str, dict] | None:
    """
    Retourne (zen_url, model_id, headers) pour un tier donné.
    Respecte la blacklist temporaire.
    None si pas de clé ou provider désactivé.
    """
    cfg = _load_routing_config()
    providers = cfg.get("providers", {})
    models = cfg.get("models", {})

    zen_cfg = providers.get("opencode_zen", {})
    zen_url, api_key, from_endpoint = _zen_provider_conn(zen_cfg)
    if not api_key:
        return None
    if not from_endpoint and not zen_cfg.get("enabled", False):
        return None

    model_cfg = models.get(tier, models.get("fast", {}))
    model_id = model_cfg.get("model_id", _DEFAULT_ZEN_MODEL)

    # Vérifier blacklist
    expiry = _zen_blacklist.get(model_id, 0.0)
    if time.time() < expiry:
        logger.debug(f"[ZenRouter] {model_id} blacklisted ({expiry - time.time():.0f}s left)")
        # Essayer le fallback
        for fallback_tier in model_cfg.get("fallback", []):
            fallback_cfg = models.get(fallback_tier, {})
            fallback_model = fallback_cfg.get("model_id", _DEFAULT_ZEN_MODEL)
            if time.time() >= _zen_blacklist.get(fallback_model, 0.0):
                model_id = fallback_model
                break
        else:
            return None

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    return zen_url, model_id, headers


def _record_zen_failure(model_id: str) -> None:
    """Incrémente le compteur d'échecs, blacklist si seuil dépassé."""
    cfg = _load_routing_config()
    threshold = cfg.get("runtime_fallback", {}).get("blacklist_on_consecutive_failures", 2)
    cooldown = cfg.get("runtime_fallback", {}).get("cooldown_seconds", 30)

    _zen_fail_counts[model_id] = _zen_fail_counts.get(model_id, 0) + 1
    if _zen_fail_counts[model_id] >= threshold:
        _zen_blacklist[model_id] = time.time() + cooldown
        logger.warning(f"[ZenRouter] {model_id} blacklisted for {cooldown}s after {threshold} failures")


def _record_zen_success(model_id: str) -> None:
    """Remet à zéro le compteur d'échecs."""
    _zen_fail_counts.pop(model_id, None)


async def call_zen(
    messages: list,
    tier: str = "standard",
    max_tokens: int = 2048,
    temperature: float = 0.7,
) -> dict:
    """
    Appel direct OpenCode Zen → réponse complète (non-streaming).
    Retourne {content, model, tier, score, tokens, status}.
    """
    candidate = get_zen_candidate(tier)
    if not candidate:
        return {"content": "", "model": "none", "tier": tier, "status": "no_provider"}

    zen_url, model_id, headers = candidate

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=10, read=120, write=30, pool=5)) as client:
            r = await client.post(
                zen_url,
                headers=headers,
                json={
                    "model": model_id,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
            )
            if r.status_code == 200:
                data = r.json()
                msg = data.get("choices", [{}])[0].get("message", {})
                content = msg.get("content") or msg.get("reasoning_content", "")
                _record_zen_success(model_id)
                return {
                    "content": content,
                    "model": model_id,
                    "tier": tier,
                    "tokens": data.get("usage", {}),
                    "status": "ok",
                }
            else:
                _record_zen_failure(model_id)
                return {"content": "", "model": model_id, "tier": tier, "status": f"http_{r.status_code}"}
    except Exception as e:
        _record_zen_failure(model_id)
        logger.warning(f"[ZenRouter] {model_id} error: {e}")
        return {"content": "", "model": model_id, "tier": tier, "status": f"error:{e}"}


async def route_and_call(
    prompt: str,
    system: str = "",
    stage: str = "chat",
    max_tokens: int = 2048,
) -> dict:
    """
    Pipeline complet : classify → tier → zen_call.
    Utilisé par /api/route et les agents internes.
    """
    cfg = _load_routing_config()
    stages = cfg.get("stages", {})

    # Stage override → tier
    tier = stages.get(stage, "standard")

    # Si pas de override, classifier la complexité
    if stage == "chat":
        tier, score = classify_complexity(prompt)
    else:
        _, score = classify_complexity(prompt)

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    result = await call_zen(messages, tier=tier, max_tokens=max_tokens)
    result["score"] = score
    result["stage"] = stage
    return result


def build_zen_candidates(messages: list, stage: str = "chat") -> list:
    """
    Construit la liste de candidats (url, model, headers) à injecter
    dans stream_llm_with_fallback() comme premier candidat Zen.
    Retourne [] si Zen non configuré.
    """
    cfg = _load_routing_config()
    stages = cfg.get("stages", {})
    models = cfg.get("models", {})
    providers = cfg.get("providers", {})

    zen_cfg = providers.get("opencode_zen", {})
    zen_url, api_key, from_endpoint = _zen_provider_conn(zen_cfg)
    if not api_key:
        return []
    if not from_endpoint and not zen_cfg.get("enabled", False):
        return []

    # Tier depuis le stage
    tier = stages.get(stage, "standard")
    if messages:
        last_user = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), "")
        if last_user:
            tier, _ = classify_complexity(last_user)

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    candidates = []
    model_cfg = models.get(tier, {})
    model_id = model_cfg.get("model_id", _DEFAULT_ZEN_MODEL)
    candidates.append((zen_url, model_id, headers))

    # Fallbacks
    for fallback_tier in model_cfg.get("fallback", []):
        fb_cfg = models.get(fallback_tier, {})
        fb_model = fb_cfg.get("model_id", _DEFAULT_ZEN_MODEL)
        if fb_model != model_id:
            candidates.append((zen_url, fb_model, headers))

    return candidates
