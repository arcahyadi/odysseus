"""
risk_classifier.py

Classifies the risk level of each tool call in the agent loop.
Used by Constitution Phase 1 to drive trace logging and destructive-action gates.
"""

from __future__ import annotations

import re
from enum import Enum


class RiskLevel(Enum):
    READ = "read"  # Read-only — no restrictions
    DRAFT = "draft"  # Draft/temp write — no gate
    WRITE = "write"  # File/DB write — mandatory log
    EXEC = "exec"  # Command execution — scope validation
    DESTRUCTIVE = "destructive"  # Deletion/drop/force — human gate


# ---------------------------------------------------------------------------
# Static tool → risk mapping
# ---------------------------------------------------------------------------

TOOL_RISK_MAP: dict[str, RiskLevel] = {
    # READ
    "read_file": RiskLevel.READ,
    "ls": RiskLevel.READ,
    "grep": RiskLevel.READ,
    "glob": RiskLevel.READ,
    "get_workspace": RiskLevel.READ,
    "search_chats": RiskLevel.READ,
    "list_served_models": RiskLevel.READ,
    "list_downloads": RiskLevel.READ,
    "list_cached_models": RiskLevel.READ,
    "list_serve_presets": RiskLevel.READ,
    "list_cookbook_servers": RiskLevel.READ,
    "list_models": RiskLevel.READ,
    "list_sessions": RiskLevel.READ,
    "vault_search": RiskLevel.READ,
    "vault_get": RiskLevel.READ,
    # WRITE
    "write_file": RiskLevel.WRITE,
    "edit_file": RiskLevel.WRITE,
    "create_document": RiskLevel.WRITE,
    "update_document": RiskLevel.WRITE,
    "edit_document": RiskLevel.WRITE,
    "suggest_document": RiskLevel.WRITE,
    "manage_notes": RiskLevel.WRITE,
    "manage_tasks": RiskLevel.WRITE,
    "manage_calendar": RiskLevel.WRITE,
    "manage_memory": RiskLevel.WRITE,
    "manage_skills": RiskLevel.WRITE,
    "update_plan": RiskLevel.WRITE,
    # EXEC
    "bash": RiskLevel.EXEC,
    "python": RiskLevel.EXEC,
    "api_call": RiskLevel.EXEC,
    "serve_model": RiskLevel.EXEC,
    "adopt_served_model": RiskLevel.EXEC,
    "trigger_research": RiskLevel.EXEC,
    "pipeline": RiskLevel.EXEC,
    "chat_with_model": RiskLevel.EXEC,
    "ask_teacher": RiskLevel.EXEC,
    "edit_image": RiskLevel.EXEC,
    # DESTRUCTIVE
    "remove_dir": RiskLevel.DESTRUCTIVE,
    "stop_served_model": RiskLevel.DESTRUCTIVE,
    "cancel_download": RiskLevel.DESTRUCTIVE,
    "manage_documents": RiskLevel.DESTRUCTIVE,  # includes delete actions
}

# ---------------------------------------------------------------------------
# Destructive bash command patterns
# ---------------------------------------------------------------------------

DESTRUCTIVE_PATTERNS = [
    r"rm\s+-[a-zA-Z]*r[a-zA-Z]*f",  # rm -rf, rm -fr, etc.
    r"rm\s+-[a-zA-Z]*f[a-zA-Z]*r",
    r"\brm\s+--force",
    r"drop\s+table",
    r"drop\s+database",
    r"git\s+push\s+--force",
    r"git\s+push\s+-f\b",
    r"git\s+reset\s+--hard",
    r"DELETE\s+FROM",
    r"truncate\s+table",
    r"format\s+[a-z]:",
    r"mkfs\.",
    r"dd\s+if=",
    r"shred\s+",
    r"wipefs\s+",
    r":(){:|:&};:",  # fork bomb
    r">\s*/dev/sd[a-z]",
    r"chmod\s+-R\s+777",
    r"chmod\s+777\s+/",
]

_COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in DESTRUCTIVE_PATTERNS]


def classify_bash(command: str) -> RiskLevel:
    """Detect destructive patterns in a bash command string."""
    for pattern in _COMPILED_PATTERNS:
        if pattern.search(command):
            return RiskLevel.DESTRUCTIVE
    return RiskLevel.EXEC


def classify_tool(tool_name: str, tool_args: dict) -> RiskLevel:
    """Classify the risk of a tool call.

    For ``bash`` and ``python`` tools, inspects the command content for
    destructive patterns. Falls back to the static TOOL_RISK_MAP, then
    defaults to EXEC for unknown tools (safest conservative assumption).
    """
    # Bash — inspect the actual command
    if tool_name in ("bash", "python"):
        command = ""
        if isinstance(tool_args, dict):
            command = tool_args.get("command", "") or tool_args.get("content", "") or ""
        elif isinstance(tool_args, str):
            command = tool_args
        level = classify_bash(command)
        return level

    # MCP tools — treat as EXEC by default (network I/O)
    if tool_name.startswith("mcp__"):
        return RiskLevel.EXEC

    return TOOL_RISK_MAP.get(tool_name, RiskLevel.EXEC)


def args_summary(tool_name: str, tool_args: dict | str, max_len: int = 120) -> str:
    """Return a safe, truncated summary of tool args (no secrets)."""
    try:
        if isinstance(tool_args, dict):
            # For bash/python show the first line of the command
            cmd = tool_args.get("command") or tool_args.get("content") or ""
            if cmd:
                first_line = str(cmd).split("\n")[0].strip()
                return first_line[:max_len]
            # Generic: key=value pairs, skip obvious secrets
            _SECRET_KEYS = {"password", "token", "secret", "api_key", "auth", "key"}
            parts = []
            for k, v in tool_args.items():
                if any(s in str(k).lower() for s in _SECRET_KEYS):
                    parts.append(f"{k}=***")
                else:
                    parts.append(f"{k}={str(v)[:40]}")
            return (", ".join(parts))[:max_len]
        return str(tool_args)[:max_len]
    except Exception:
        return f"<{tool_name}>"
