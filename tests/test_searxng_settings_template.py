"""The searxng settings template must stay re-renderable and keep a working engine set.

The upstream default engines (brave / duckduckgo / startpage) return
CAPTCHA or rate-limit pages from the deployment host, which left every default
query with zero results (2026-09-24). The template enables engines verified to
answer, and carries a version marker the compose entrypoint uses to re-render
an existing named volume when the template changes.
"""
from pathlib import Path

import yaml

TEMPLATE = Path("config/searxng/settings.yml")


def _settings():
    return yaml.safe_load(TEMPLATE.read_text(encoding="utf-8"))


def test_template_has_version_marker_on_first_line():
    first = TEMPLATE.read_text(encoding="utf-8").splitlines()[0]
    assert first.startswith("# odysseus-searxng-settings: ")


def test_compose_entrypoint_rerenders_on_marker_change():
    compose = Path("docker-compose.yml").read_text(encoding="utf-8")
    assert "^# odysseus-searxng-settings:" in compose
    assert 'grep -qxF "$$marker" "$$live"' in compose


def test_secret_placeholder_and_json_format_kept():
    s = _settings()
    assert s["server"]["secret_key"] == "__SEARXNG_SECRET__"
    assert "json" in s["search"]["formats"]


def test_verified_engines_enabled_and_blocked_ones_disabled():
    engines = {e["name"]: e["disabled"] for e in _settings()["engines"]}
    assert engines["bing"] is False
    for blocked in ("brave", "duckduckgo", "startpage"):
        assert engines[blocked] is True
