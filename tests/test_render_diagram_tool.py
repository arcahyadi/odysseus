"""Bloc F — render_diagram agent tool (Kroki).

The Kroki container already ships in docker-compose (KROKI_ENABLED=true) but had
NO LLM-callable tool — `tools: []` by design in mcp_manager. The user wants the
model to render explanatory diagrams easily. This tool is the missing seam.

Native-first: it reuses the *exact* Kroki encoding already proven in
routes/mcp_tools_routes.py (deflate level-9 + base64url) and the *exact* image
return path proven by generate_image — save PNG under GENERATED_IMAGES_DIR and
return an `/api/generated-image/{file}` URL so the chat renders it via the
native image bubble (result["image_url"] forwarding in agent_loop).

Kill-switch: gated by KROKI_ENABLED so the base product is byte-identical when
the service is off.
"""

import asyncio
import base64
import json
import zlib

from src.agent_tools.diagram_tools import (
    RenderDiagramTool,
    kroki_encode,
    kroki_url,
)


def test_kroki_encode_is_deflate_base64url_roundtrip():
    src = "graph TD; A-->B"
    encoded = kroki_encode(src)
    # URL-safe base64 alphabet only (no +,/)
    assert "+" not in encoded and "/" not in encoded
    # Decodes back to the original diagram source
    decoded = zlib.decompress(base64.urlsafe_b64decode(encoded)).decode("utf-8")
    assert decoded == src


def test_kroki_url_builds_type_and_format_path():
    encoded = kroki_encode("A-->B")
    url = kroki_url("mermaid", "png", encoded, base_url="http://kroki:8000")
    assert url == f"http://kroki:8000/mermaid/png/{encoded}"


def test_execute_disabled_returns_error(monkeypatch):
    monkeypatch.setenv("KROKI_ENABLED", "false")
    out = asyncio.run(RenderDiagramTool().execute("graph TD; A-->B", {}))
    assert out["exit_code"] == 1
    assert "disabled" in out["error"].lower()


def test_execute_png_saves_and_returns_image_url(monkeypatch, tmp_path):
    monkeypatch.setenv("KROKI_ENABLED", "true")
    # Redirect the on-disk image dir into tmp
    import src.agent_tools.diagram_tools as dt

    monkeypatch.setattr(dt, "GENERATED_IMAGES_DIR", str(tmp_path))

    png_bytes = b"\x89PNG\r\n\x1a\nFAKEPNGDATA"

    class _Resp:
        status_code = 200
        content = png_bytes
        text = ""

    captured = {}

    def _fake_get(url, timeout=15.0):
        captured["url"] = url
        return _Resp()

    monkeypatch.setattr(dt.httpx, "get", _fake_get)

    payload = json.dumps(
        {
            "content": "graph TD; A-->B",
            "diagram_type": "mermaid",
            "output_format": "png",
        }
    )
    out = asyncio.run(RenderDiagramTool().execute(payload, {}))

    assert out["exit_code"] == 0
    # image_url points at the native generated-image route so chat renders it
    assert out["image_url"].startswith("/api/generated-image/")
    assert out["image_url"].endswith(".png")
    # File actually written with the Kroki bytes
    fname = out["image_url"].rsplit("/", 1)[-1]
    saved = tmp_path / fname
    assert saved.read_bytes() == png_bytes
    # Correct Kroki path was requested
    assert "/mermaid/png/" in captured["url"]


def test_execute_svg_returns_inline_text(monkeypatch):
    monkeypatch.setenv("KROKI_ENABLED", "true")
    import src.agent_tools.diagram_tools as dt

    class _Resp:
        status_code = 200
        content = b""
        text = "<svg>diagram</svg>"

    monkeypatch.setattr(dt.httpx, "get", lambda url, timeout=15.0: _Resp())

    payload = json.dumps({"content": "A-->B", "output_format": "svg"})
    out = asyncio.run(RenderDiagramTool().execute(payload, {}))
    assert out["exit_code"] == 0
    assert "<svg>" in out["output"]
    assert "image_url" not in out


def test_execute_kroki_error_surfaces_status(monkeypatch):
    monkeypatch.setenv("KROKI_ENABLED", "true")
    import src.agent_tools.diagram_tools as dt

    class _Resp:
        status_code = 400
        content = b""
        text = "Syntax error in diagram"

    monkeypatch.setattr(dt.httpx, "get", lambda url, timeout=15.0: _Resp())

    out = asyncio.run(RenderDiagramTool().execute("bad diagram", {}))
    assert out["exit_code"] == 1
    assert "400" in out["error"]


def test_execute_empty_source_errors(monkeypatch):
    monkeypatch.setenv("KROKI_ENABLED", "true")
    out = asyncio.run(RenderDiagramTool().execute("   ", {}))
    assert out["exit_code"] == 1
