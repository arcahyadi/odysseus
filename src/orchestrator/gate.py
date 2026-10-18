"""Catastrophic-command gate (Milestone 2, P4).

The destructive detection in tool_execution.py historically only LOGGED and
then executed anyway. This module provides a real block decision for
catastrophic SHELL commands (rm -rf, fork bomb, mkfs, dd, drop database, ...)
using the existing risk_classifier patterns.

It intentionally does NOT block the explicit destructive TOOLS (delete_file,
remove_dir, stop_served_model, ...) — those are user-facing operations with
their own semantics; blocking them would break the product.
"""

from __future__ import annotations

import os

from src.risk_classifier import RiskLevel, classify_bash

# Live shell tools (tool_schemas.py). `run_command` was a phantom alias — no
# such tool is ever defined or dispatched — so it's dropped from the guard (M3.4).
_SHELL_TOOLS = {"bash", "python"}


def gate_enabled() -> bool:
    """The gate is on unless ODYSSEUS_DESTRUCTIVE_GATE is set to a false-y value."""
    val = os.getenv("ODYSSEUS_DESTRUCTIVE_GATE", "on").strip().lower()
    return val not in {"off", "0", "false", "no"}


def _extract_command(tool_args) -> str:
    if isinstance(tool_args, str):
        return tool_args
    if isinstance(tool_args, dict):
        return str(tool_args.get("command") or tool_args.get("content") or "")
    return ""


def should_block_destructive(tool_name: str, tool_args) -> str | None:
    """Return a block reason for catastrophic shell commands, else None.

    Pure function: does not read env. Enforcement callers should also check
    gate_enabled() to honour the kill-switch.
    """
    if tool_name not in _SHELL_TOOLS:
        return None
    command = _extract_command(tool_args)
    if not command:
        return None
    if classify_bash(command) == RiskLevel.DESTRUCTIVE:
        first = command.split("\n")[0].strip()[:120]
        return f"Commande catastrophique bloquée par le gate destructif : {first!r}"
    return None
