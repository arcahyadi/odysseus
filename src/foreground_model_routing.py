"""Explicit foreground Chat and Agent model-routing policy."""

from dataclasses import dataclass
from typing import Any, Collection, Dict, FrozenSet, Optional, Tuple

from src.endpoint_resolver import (
    endpoint_cost_tracked,
    resolve_fallback_entries,
    resolve_fallback_entries_with_descriptors,
    resolve_route_descriptor,
    resolve_route_descriptor_by_id,
)

_DEFAULT_FALLBACK_ENTRY_RESOLVER = resolve_fallback_entries


FOREGROUND_FALLBACK_ENABLED_KEY = "foreground_fallback_enabled"
FOREGROUND_FALLBACK_LIST_KEY = "foreground_model_fallbacks"
FOREGROUND_AVAILABILITY_STATUSES: FrozenSet[int] = frozenset({
    408, 425, 429, 500, 502, 503, 504, 507, 508, 529,
})
MAX_FOREGROUND_FALLBACKS = 10


@dataclass(frozen=True)
class ForegroundModelPolicy:
    """Resolved per-user foreground fallback policy."""

    enabled: bool = False
    fallback_candidates: Tuple[tuple, ...] = ()
    fallback_descriptors: Tuple[dict, ...] = ()
    eligible_statuses: FrozenSet[int] = FOREGROUND_AVAILABILITY_STATUSES
    fallback_on_empty: bool = False
    # Extra same-model attempts when a stream ends with no substantive output.
    # An empty completion is usually transient (thinking budget exhaustion),
    # so the selected model gets one immediate retry before the chain walks
    # the fallback candidates — a retry keeps the user's selection where a
    # fallback would abandon it for the rest of the agent run.
    empty_retry_attempts: int = 0


def _load_policy_preferences(owner: Optional[str]) -> dict:
    """Load only preferences that explicitly belong to ``owner``.

    The generic preferences loader intentionally treats a legacy flat store as
    the single-user preferences object.  That compatibility must not cross an
    authentication transition: once a named owner is present, foreground
    fallback consent exists only in an actual ``_users[owner]`` dictionary.
    """

    from routes import prefs_routes

    if owner is None:
        prefs = prefs_routes._load_for_user(None)
        return dict(prefs) if isinstance(prefs, dict) else {}

    raw = prefs_routes._load()
    users = raw.get("_users") if isinstance(raw, dict) else None
    if not isinstance(users, dict):
        return {}
    prefs = users.get(owner)
    return dict(prefs) if isinstance(prefs, dict) else {}


def resolve_foreground_model_policy(
    owner: Optional[str] = None,
    allowed_models: Optional[Collection[str]] = None,
) -> ForegroundModelPolicy:
    """Resolve an explicit owner-scoped policy, failing closed to strict mode.

    The policy is stored in user preferences even when authentication is
    disabled. Historical ``default_model_fallbacks`` values are deliberately
    unrelated and are never read or migrated.
    """

    try:
        prefs = _load_policy_preferences(owner)
    except Exception:
        return ForegroundModelPolicy()

    if prefs.get(FOREGROUND_FALLBACK_ENABLED_KEY) is not True:
        return ForegroundModelPolicy()

    entries = prefs.get(FOREGROUND_FALLBACK_LIST_KEY)
    if not isinstance(entries, list) or not entries:
        return ForegroundModelPolicy()
    if allowed_models is not None:
        allowed = frozenset(allowed_models)
        entries = [
            entry for entry in entries
            if (
                isinstance(entry, dict)
                and isinstance(entry.get("model"), str)
                and entry.get("model") in allowed
            )
        ]
        if not entries:
            return ForegroundModelPolicy()
    entries = entries[:MAX_FOREGROUND_FALLBACKS]

    if resolve_fallback_entries is not _DEFAULT_FALLBACK_ENTRY_RESOLVER:
        # Preserve the long-standing resolver seam used by downstream tests and
        # integrations. Production uses the descriptor-aware resolver below.
        compatibility_candidates = resolve_fallback_entries(
            entries,
            owner=owner,
            require_exact_model=True,
        )
        # Known limitation of this test-only seam: alignment matches on model
        # alone, so when two entries share a model and the resolver skips the
        # first, the surviving candidate inherits the skipped entry's
        # endpoint_id. Production uses the descriptor-aware branch below,
        # which is unaffected.
        resolved_routes = []
        remaining_entries = list(entries)
        for candidate in compatibility_candidates:
            matching_index = next(
                (
                    index for index, entry in enumerate(remaining_entries)
                    if isinstance(entry, dict)
                    and entry.get("model") == candidate[1]
                ),
                None,
            )
            matching_entry = (
                remaining_entries.pop(matching_index)
                if matching_index is not None
                else {}
            )
            descriptor = {
                "endpoint_id": matching_entry.get("endpoint_id"),
                "endpoint_label": matching_entry.get("endpoint_id") or "Fallback route",
                "endpoint_cost_tracked": endpoint_cost_tracked(candidate[0]),
            }
            resolved_routes.append((candidate, descriptor))
    else:
        resolved_routes = resolve_fallback_entries_with_descriptors(
            entries,
            owner=owner,
            require_exact_model=True,
        )
    candidates = [candidate for candidate, _descriptor in resolved_routes]
    if not candidates:
        return ForegroundModelPolicy()

    return ForegroundModelPolicy(
        enabled=True,
        fallback_candidates=tuple(candidates),
        fallback_descriptors=tuple(
            dict(descriptor) for _candidate, descriptor in resolved_routes
        ),
        # An opted-in chain treats an empty round as recoverable: retry the
        # same model once, then walk the configured candidates, and only then
        # surface the 502. (2026-08-25: thinker14b agent rounds died on the
        # first empty completion because fallback_on_empty was never set.)
        fallback_on_empty=True,
        empty_retry_attempts=1,
    )


def resolve_foreground_fallback_candidates(owner: Optional[str] = None) -> list:
    """Return only candidates explicitly enabled by the current user."""

    return list(resolve_foreground_model_policy(owner).fallback_candidates)


def foreground_fallback_notice_line(
    selected_model: Optional[str],
    answered_model: Optional[str],
    answered_by_label: Optional[str] = None,
) -> str:
    """One unobtrusive line announcing that a fallback, not the selected
    model, answered the request.

    A foreground swap used to be silent in the rendered reply: only the
    ``fallback`` SSE event and post-hoc metadata recorded it, so a paid
    provider answering under a dead local model's name was invisible in the
    chat transcript. Consumers emit this line exactly once per request, before
    the answering model's first content delta.

    Names the answering model; when the swap kept the SAME model on another
    endpoint/account (the model names would read as a no-op), the endpoint
    label carries the distinction instead. Contains no failure detail or
    provider payload — just identities the user already knows.
    """
    selected = str(selected_model or "").strip()
    answered = str(answered_model or "").strip()
    label = str(answered_by_label or "").strip()
    if answered and answered != selected:
        who = answered
    elif label:
        who = label
    elif answered:
        who = answered
    else:
        who = "a fallback route"
    if selected:
        return f"[Model fallback: {selected} unavailable; answered by {who}.]"
    return f"[Model fallback: answered by {who}.]"


def build_foreground_model_candidates(
    endpoint_url: str,
    model: str,
    headers: Optional[Dict[str, Any]] = None,
    owner: Optional[str] = None,
    policy: Optional[ForegroundModelPolicy] = None,
) -> list:
    """Build the ordered candidate list for a foreground request."""

    policy = policy or resolve_foreground_model_policy(owner)
    primary = (endpoint_url, model, headers or {})
    candidates = [primary]
    for candidate in policy.fallback_candidates:
        if candidate not in candidates:
            candidates.append(candidate)
    return candidates


def build_foreground_route_descriptors(
    endpoint_url: str,
    model: str,
    headers: Optional[Dict[str, Any]] = None,
    owner: Optional[str] = None,
    policy: Optional[ForegroundModelPolicy] = None,
    selected_endpoint_id: Optional[str] = None,
) -> list:
    """Build safe route metadata parallel to foreground candidates."""

    policy = policy or resolve_foreground_model_policy(owner)
    selected = None
    if selected_endpoint_id:
        selected = resolve_route_descriptor_by_id(
            selected_endpoint_id,
            endpoint_url,
            model,
            headers or {},
            owner=owner,
        )
    if selected is None:
        selected = resolve_route_descriptor(endpoint_url, model, headers or {}, owner=owner)
    primary = (endpoint_url, model, headers or {})
    candidates = [primary]
    descriptors = [selected]
    for candidate, descriptor in zip(
        policy.fallback_candidates,
        policy.fallback_descriptors,
    ):
        if candidate in candidates:
            continue
        candidates.append(candidate)
        descriptors.append(dict(descriptor))
    return descriptors
