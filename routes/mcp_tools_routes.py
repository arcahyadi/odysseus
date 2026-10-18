"""Routes pour les MCP tools externes (Kroki).

NOTE: Scrapling is NOT proxied here. Its earlier `/scrape` + `/spider` proxies
hit REST endpoints (/extract, /spider) that Scrapling's MCP server never
exposes. Scrapling is now wired the correct way — as a real MCP server through
src/mcp_manager.py (EXTERNAL_MCP_SERVERS + connect_external_enabled), so its
real tools (get/fetch/stealthy_fetch/...) surface to the agent as
mcp__scrapling__*. Kroki stays here as a REST render (also fronted by the
native render_diagram agent tool).
"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/tools", tags=["mcp-tools"])


class DiagramRequest(BaseModel):
    content: str
    diagram_type: str = "mermaid"  # mermaid, plantuml, graphviz, etc.
    output_format: str = "svg"


@router.post("/diagram")
async def render_diagram(req: DiagramRequest):
    """Kroki — render un diagramme texte en SVG/PNG."""
    try:
        import base64
        import zlib

        import httpx

        # Encodage Kroki : deflate + base64url
        compressed = zlib.compress(req.content.encode(), level=9)
        encoded = base64.urlsafe_b64encode(compressed).decode()

        url = f"http://localhost:8700/{req.diagram_type}/{req.output_format}/{encoded}"
        resp = httpx.get(url, timeout=15.0)

        if req.output_format == "svg":
            return {"svg": resp.text, "url": url}
        else:
            return {"image_b64": base64.b64encode(resp.content).decode(), "url": url}
    except Exception as e:
        return {"error": str(e), "hint": "Kroki démarre automatiquement avec docker compose up"}


@router.get("/available")
async def list_available_tools():
    """Liste les MCP tools disponibles et leur statut."""
    import httpx

    tools_status = {}
    # Any HTTP response (incl. 4xx) means the service is listening → "online".
    # Scrapling's MCP endpoint is /mcp (a GET without a session yields 4xx, which
    # still proves it's up); Kroki answers on its root.
    services = {
        "scrapling": "http://localhost:8800/mcp",
        "kroki": "http://localhost:8700/health",
        "supabase": "http://localhost:8900/mcp",
        "serena": "http://localhost:8765/health",
    }
    for name, health_url in services.items():
        try:
            r = httpx.get(health_url, timeout=2.0)
            # 5xx = up but erroring; anything that returned a status = listening.
            tools_status[name] = "online" if r.status_code < 500 else "error"
        except Exception:
            tools_status[name] = "offline"
    return {"tools": tools_status}
