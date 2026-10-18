"""diagram_tools.py — render_diagram agent tool (Kroki).

Turns diagram *source text* (mermaid, plantuml, graphviz, d2, ...) into a
rendered image the LLM can drop into a chat explanation.

Native-first design (zero redundancy):
  - Encoding reuses the exact Kroki scheme already proven in
    routes/mcp_tools_routes.py: zlib deflate level-9 + base64url → GET path.
  - Image return reuses the exact generate_image path: save the PNG under
    GENERATED_IMAGES_DIR and return an `/api/generated-image/{file}` URL, which
    the agent loop lifts from result["image_url"] into the native image bubble.

Kill-switch: gated by KROKI_ENABLED (default on, matching .env.example). When
off, the tool refuses cleanly — the base product is unchanged and no network
call is made.
"""

import asyncio
import base64
import json
import os
import uuid
import zlib

import httpx

from src.constants import GENERATED_IMAGES_DIR

# Kroki base URL. Native config (mcp_manager.EXTERNAL_MCP_SERVERS["kroki"]) uses
# localhost:8700; inside Docker the app reaches the service at kroki:8000. Allow
# an env override so both host-run and in-network deployments work.
_DEFAULT_KROKI_URL = "http://localhost:8700"

# Output formats we accept from the model. PNG → saved image bubble; SVG →
# inline text the model can embed/inspect.
_VALID_FORMATS = ("png", "svg")


def _kroki_enabled() -> bool:
    return os.getenv("KROKI_ENABLED", "off").strip().lower() in ("1", "true", "yes", "on")


def _kroki_base_url() -> str:
    return (os.getenv("KROKI_URL", "") or _DEFAULT_KROKI_URL).rstrip("/")


def kroki_encode(content: str) -> str:
    """Deflate (level 9) + urlsafe-base64 — the Kroki GET encoding."""
    compressed = zlib.compress(content.encode("utf-8"), level=9)
    return base64.urlsafe_b64encode(compressed).decode("ascii")


def kroki_url(diagram_type: str, output_format: str, encoded: str, base_url: str | None = None) -> str:
    """Build the Kroki request URL: {base}/{type}/{format}/{encoded}."""
    base = (base_url or _kroki_base_url()).rstrip("/")
    return f"{base}/{diagram_type}/{output_format}/{encoded}"


class RenderDiagramTool:
    """Render diagram source text into an image via Kroki."""

    async def execute(self, content: str, ctx: dict) -> dict:
        if not _kroki_enabled():
            return {
                "error": (
                    "render_diagram: Kroki is disabled. Set KROKI_ENABLED=true and "
                    "start the kroki service (docker compose up) to render diagrams."
                ),
                "exit_code": 1,
            }

        raw = (content or "").strip()
        diagram_type = "mermaid"
        output_format = "png"
        source = raw

        if raw.startswith("{"):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    source = str(parsed.get("content") or parsed.get("source") or parsed.get("diagram") or "").strip()
                    dt = parsed.get("diagram_type") or parsed.get("type")
                    if isinstance(dt, str) and dt.strip():
                        diagram_type = dt.strip().lower()
                    of = parsed.get("output_format") or parsed.get("format")
                    if isinstance(of, str) and of.strip().lower() in _VALID_FORMATS:
                        output_format = of.strip().lower()
            except json.JSONDecodeError:
                source = raw

        if not source:
            return {
                "error": "render_diagram: provide diagram source text (e.g. mermaid 'graph TD; A-->B').",
                "exit_code": 1,
            }

        encoded = kroki_encode(source)
        url = kroki_url(diagram_type, output_format, encoded)

        loop = asyncio.get_running_loop()
        try:
            resp = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: httpx.get(url, timeout=15.0)),
                timeout=20,
            )
        except TimeoutError:
            return {"error": "render_diagram: Kroki timed out after 20s.", "exit_code": 1}
        except Exception as e:
            return {
                "error": (
                    f"render_diagram: could not reach Kroki ({type(e).__name__}: {e}). Is the kroki service running?"
                ),
                "exit_code": 1,
            }

        if getattr(resp, "status_code", 500) >= 400:
            detail = (getattr(resp, "text", "") or "")[:300]
            return {
                "error": f"render_diagram: Kroki {resp.status_code} — {detail or 'render failed'}",
                "exit_code": 1,
            }

        # SVG: return inline text the model can embed directly.
        if output_format == "svg":
            return {"output": resp.text, "exit_code": 0}

        # PNG: save under GENERATED_IMAGES_DIR and return the native image URL so
        # the chat renders it via buildImageBubble (result["image_url"]).
        os.makedirs(GENERATED_IMAGES_DIR, exist_ok=True)
        filename = f"{uuid.uuid4().hex[:12]}.png"
        path = os.path.join(GENERATED_IMAGES_DIR, filename)
        with open(path, "wb") as f:
            f.write(resp.content)

        pub_base = ""
        try:
            from src.settings import get_setting

            pub_base = (get_setting("app_public_url", "") or "").rstrip("/")
        except Exception:
            pub_base = ""
        image_url = f"{pub_base}/api/generated-image/{filename}"

        return {
            "output": f"Rendered {diagram_type} diagram.\nDirect link: {image_url}",
            "image_url": image_url,
            "image_prompt": f"{diagram_type} diagram",
            "exit_code": 0,
        }
