"""Parse a .opencode agent Markdown file into an immutable AgentSpec.

An agent file is either:
  1. YAML frontmatter delimited by leading '---' lines, followed by a Markdown
     body used as the system prompt; or
  2. A bare Markdown file with no frontmatter — the whole file is the prompt and
     the agent name is derived from the filename stem.

This module has no side effects and no network calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class AgentSpec:
    """Immutable description of one orchestrated agent."""

    name: str
    description: str = ""
    prompt: str = ""
    tools: list[str] = field(default_factory=list)
    model: str | None = None
    mode: str | None = None
    source_path: str = ""


def _split_frontmatter(text: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body). If there is no leading '---' block,
    return ({}, text)."""
    if not text.lstrip().startswith("---"):
        return {}, text

    stripped = text.lstrip("\n")
    if not stripped.startswith("---"):
        return {}, text

    parts = stripped.split("\n")
    # parts[0] == '---'. Find the closing '---'.
    for idx in range(1, len(parts)):
        if parts[idx].strip() == "---":
            fm_raw = "\n".join(parts[1:idx])
            body = "\n".join(parts[idx + 1 :])
            try:
                fm = yaml.safe_load(fm_raw) or {}
            except yaml.YAMLError:
                fm = {}
            if not isinstance(fm, dict):
                fm = {}
            return fm, body.lstrip("\n")
    # No closing fence — treat as no frontmatter.
    return {}, text


def parse_agent_spec(path) -> AgentSpec:
    """Parse one agent Markdown file into an AgentSpec."""
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    fm, body = _split_frontmatter(text)

    name = fm.get("name") or p.stem
    description = fm.get("description") or ""
    if isinstance(description, str):
        description = description.strip()

    tools_raw = fm.get("tools") or []
    tools = [str(t).strip() for t in tools_raw] if isinstance(tools_raw, list) else []

    return AgentSpec(
        name=str(name),
        description=str(description),
        prompt=body.strip(),
        tools=tools,
        model=fm.get("model"),
        mode=fm.get("mode"),
        source_path=str(p),
    )
