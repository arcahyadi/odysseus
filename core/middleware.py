# src/middleware.py
# Shared middleware, decorators, and request helpers

import logging
import os
import secrets
from collections.abc import Mapping

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.routing import get_route_path

from src.owner_identity import INTERNAL_TOOL_USER, auth_disabled


logger = logging.getLogger(__name__)


# Per-process token that lets the in-app tool layer hit admin-gated
# routes via HTTP loopback (the agent's tool calls don't carry the
# admin user's session cookie). Never persisted or exposed externally.
#
# When ODYSSEUS_INTERNAL_TOKEN is unset we mint a random per-process
# value — safe by default. Operators who *do* set it opt into an admin
# bypass header (X-Odysseus-Internal-Token) that must be treated like
# a password; the resolver below refuses to accept short or guessable
# values, falling back to a random token so the bypass cannot be
# silently opened by an example copied from the internet.
_MIN_INTERNAL_TOKEN_LEN = 32


def _looks_weak(token: str) -> str | None:
    """Return a short reason string when the operator-provided token is
    unsafe, or None when it's acceptable."""
    stripped = token.strip()
    if not stripped:
        return "empty"
    if len(stripped) < _MIN_INTERNAL_TOKEN_LEN:
        return f"shorter than {_MIN_INTERNAL_TOKEN_LEN} chars"
    if len(set(stripped)) < 4:
        return "insufficient character variety"
    return None


def _resolve_internal_tool_token() -> tuple[str, str | None]:
    """Return (token, warning_reason). Reason is None when we minted a
    random token or when the operator's override was strong enough."""
    operator_val = os.environ.get("ODYSSEUS_INTERNAL_TOKEN")
    if not operator_val:
        return secrets.token_hex(32), None
    reason = _looks_weak(operator_val)
    if reason:
        return secrets.token_hex(32), reason
    return operator_val.strip(), None


INTERNAL_TOOL_TOKEN, _INTERNAL_TOKEN_REJECT_REASON = _resolve_internal_tool_token()
INTERNAL_TOOL_HEADER = "X-Odysseus-Internal-Token"
# Pseudo-username on in-process tool-loopback requests; require_admin trusts it and it is reserved.
INTERNAL_TOOL_USER = "internal-tool"

if _INTERNAL_TOKEN_REJECT_REASON:
    logger.warning(
        "ODYSSEUS_INTERNAL_TOKEN was set but rejected (%s). "
        "Falling back to a per-process random token — external tools will "
        "not be able to authenticate via X-Odysseus-Internal-Token until "
        "you set a value of at least %d chars that isn't on the weak list.",
        _INTERNAL_TOKEN_REJECT_REASON,
        _MIN_INTERNAL_TOKEN_LEN,
    )
elif os.environ.get("ODYSSEUS_INTERNAL_TOKEN"):
    logger.info(
        "ODYSSEUS_INTERNAL_TOKEN is set; require_admin will accept requests "
        "carrying the X-Odysseus-Internal-Token header. Treat this value "
        "like a password and rotate it if it ever appears in a log, chat, "
        "or screenshot."
    )


def is_cors_preflight(method: str, headers) -> bool:
    """True for a genuine CORS preflight: an OPTIONS request carrying the
    Access-Control-Request-Method header. Such requests are credential-less by
    design and must reach CORSMiddleware to be answered -- gating them on auth
    401s the preflight and breaks every cross-origin browser/WebView client.
    Pure so it can be unit-tested without standing up the app."""
    return method == "OPTIONS" and "access-control-request-method" in headers


def get_application_route_path(scope: Mapping[str, object]) -> str:
    """Return the application-relative path used by Starlette routing.

    Uvicorn prefixes ``scope["path"]`` with a configured ASGI ``root_path``;
    Starlette removes that prefix before matching routes. Middleware policy
    must use the same path form or a deployment prefix can change which policy
    applies to an otherwise unchanged application route.
    """
    return get_route_path(scope)


def with_asgi_root_path(scope: Mapping[str, object], path: str) -> str:
    """Prefix an application path for a client-facing redirect target."""
    root_path = scope.get("root_path", "")
    if not isinstance(root_path, str) or not root_path:
        return path
    return f"{root_path.rstrip('/')}{path}"


def path_is_route_or_child(path: str, prefix: str) -> bool:
    """Return whether ``path`` is exactly ``prefix`` or below that route."""
    return path == prefix or path.startswith(prefix + "/")


def is_cors_preflight(method: str, headers) -> bool:
    """True for a genuine CORS preflight: an OPTIONS request carrying the
    Access-Control-Request-Method header. Such requests are credential-less by
    design and must reach CORSMiddleware to be answered -- gating them on auth
    401s the preflight and breaks every cross-origin browser/WebView client.
    Pure so it can be unit-tested without standing up the app."""
    return method == "OPTIONS" and "access-control-request-method" in headers


def require_admin(request: Request):
    """Raise 403 if the current user isn't an admin.
    Allows access when auth is explicitly disabled, or when the request carries
    the in-process internal-tool token used by loopback agent tools.
    """
    # In-process bypass for tool-layer loopback calls. Two paths:
    # (a) header-direct (caller set X-Odysseus-Internal-Token), or
    # (b) the auth middleware already validated the token and stamped
    #     request.state.current_user = "internal-tool".
    try:
        hdr = request.headers.get(INTERNAL_TOOL_HEADER)
        if hdr and secrets.compare_digest(hdr, INTERNAL_TOOL_TOKEN):
            return
        if getattr(request.state, "current_user", None) == INTERNAL_TOOL_USER:
            return
    except Exception:
        pass

    auth_mgr = getattr(request.app.state, "auth_manager", None)
    if auth_disabled():
        return
    if not auth_mgr or not auth_mgr.is_configured:
        raise HTTPException(403, "Admin only")
    user = getattr(request.state, "current_user", None)
    if not user or not auth_mgr.is_admin(user):
        raise HTTPException(403, "Admin only")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add standard security headers to all responses."""

    async def dispatch(self, request: Request, call_next) -> Response:
        # Generate a per-request nonce for inline scripts
        nonce = secrets.token_hex(16)
        request.state.csp_nonce = nonce

        response = await call_next(request)
        path = request.url.path

        # Tool render endpoints
        is_tool_render = path.startswith("/api/tools/") and path.endswith("/render")
        # Document library PDF preview endpoint
        is_document_pdf_preview = path.startswith("/api/document/") and path.endswith("/render-pdf")
        # Visual report pages are self-contained HTML — need inline scripts + external images
        is_report = path.startswith("/api/research/report/")

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(self), geolocation=()"

        is_https = (
            request.url.scheme == "https"
            or request.headers.get("X-Forwarded-Proto") == "https"
        )
        if is_https:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        if is_report:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; "
                "font-src 'self'; "
                "img-src 'self' data: blob: https:; "
                "connect-src 'self'; "
                "frame-ancestors 'none'"
            )
        elif is_tool_render:
            # Skip framing headers for tools.
            pass
        elif is_document_pdf_preview:
            response.headers["X-Frame-Options"] = "SAMEORIGIN"
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; "
                "frame-ancestors 'self'"
            )
        else:
            response.headers["X-Frame-Options"] = "DENY"
            # NOTE: `style-src 'unsafe-inline'` is intentionally retained.
            # `static/index.html` and `static/login.html` ship inline <style>
            # blocks, and several JS modules build runtime `style=""` attrs.
            # Migrating to nonce-only requires templating the HTML files +
            # auditing every JS-set style attribute. Since inline styles
            # don't execute script, the residual risk is visual-only.
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                # script-src still allows cdn.jsdelivr.net for Pyodide, which
                # codeRunner.js loads lazily (~200 MB of wheel bundles; not
                # vendored). KaTeX + Mermaid are local since 2026-10-03, so
                # style-src and font-src no longer need the CDN.
                f"script-src 'self' 'nonce-{nonce}' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "font-src 'self' https://cdn.jsdelivr.net; "
                "img-src 'self' data: blob: https:; "
                "media-src 'self' blob:; "
                "connect-src 'self'; "
                "frame-src 'self'; "
                "frame-ancestors 'none'"
            )
        return response
